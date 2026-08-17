package validators

import (
	"crypto/ed25519"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math/big"
	"strings"

	testsmcp "github.com/endomorphosis/Mcp-Plus-Plus/tests-go"
)

// DelegationProof@1 interface labels (MCPP-041).
const (
	DelegationProofInterface = "DelegationProof@1"
	CanonicalAlgorithm       = "mcpp-jcs-v1"
	SignatureAlgEdDSA        = "EdDSA"
	SignatureAlgEd25519      = "Ed25519"
)

// LevelResult is one conformance-level outcome (ADR-0003).
type LevelResult struct {
	Valid      bool     `json:"valid"`
	Errors     []string `json:"errors"`
	ReasonCode string   `json:"reason_code,omitempty"`
}

// DelegationValidationResult reports structural and cryptographic levels separately.
type DelegationValidationResult struct {
	IsValid        bool                   `json:"is_valid"`
	Structural     LevelResult            `json:"structural"`
	Cryptographic  LevelResult            `json:"cryptographic"`
	Conformance    string                 `json:"conformance_level,omitempty"`
	Interface      string                 `json:"interface"`
	Token          *testsmcp.UCANToken    `json:"token,omitempty"`
	Chain          *testsmcp.DelegationChain `json:"chain,omitempty"`
	Metadata       map[string]interface{} `json:"metadata,omitempty"`
	Errors         []string               `json:"errors,omitempty"`
}

// UCANValidator validates UCAN Delegation (Profile C) messages.
//
// SPEC: UCAN-Delegation.md § Capability Chains
// Crypto: ADR-0002 Ed25519 over mcpp-jcs-v1 canonical bytes (DelegationProof@1)
type UCANValidator struct {
	base               *BaseMCPValidator
	issuerPublicKeys   map[string]interface{}
	requireSignatures  bool
}

// NewUCANValidator creates a new UCAN delegation validator.
func NewUCANValidator() *UCANValidator {
	return &UCANValidator{
		base:             NewBaseMCPValidator(),
		issuerPublicKeys: map[string]interface{}{},
	}
}

// WithIssuerPublicKeys registers verification keys by issuer DID.
func (v *UCANValidator) WithIssuerPublicKeys(keys map[string]interface{}) *UCANValidator {
	if keys != nil {
		v.issuerPublicKeys = keys
	}
	return v
}

// WithRequireSignatures toggles fail-closed signature requirement.
func (v *UCANValidator) WithRequireSignatures(require bool) *UCANValidator {
	v.requireSignatures = require
	return v
}

// ValidateUCANToken validates a UCAN token (structural + crypto when signature present).
//
// SPEC: UCAN-Delegation.md, MUST have iss, aud, att, and exp fields
func (v *UCANValidator) ValidateUCANToken(data []byte) (*testsmcp.UCANToken, error) {
	res, err := v.ValidateUCANTokenLevels(data, nil, false)
	if err != nil {
		return nil, err
	}
	if !res.IsValid {
		if len(res.Errors) > 0 {
			return nil, fmt.Errorf("%s", res.Errors[0])
		}
		return nil, fmt.Errorf("validation failed")
	}
	return res.Token, nil
}

// ValidateUCANTokenLevels validates structural and cryptographic levels for a token.
func (v *UCANValidator) ValidateUCANTokenLevels(data []byte, issuerKeys map[string]interface{}, requireSig bool) (*DelegationValidationResult, error) {
	keys := mergeKeys(v.issuerPublicKeys, issuerKeys)
	require := v.requireSignatures || requireSig

	var raw map[string]interface{}
	if err := json.Unmarshal(data, &raw); err != nil {
		// Try compact string token (JSON string).
		var s string
		if err2 := json.Unmarshal(data, &s); err2 == nil {
			return v.validateCompactLevels(s, 0, keys, require), nil
		}
		return &DelegationValidationResult{
			IsValid:       false,
			Interface:     DelegationProofInterface,
			Structural:    LevelResult{Valid: false, Errors: []string{"invalid JSON: " + err.Error()}, ReasonCode: "invalid_json"},
			Cryptographic: LevelResult{Valid: false, Errors: []string{"structural_failed"}, ReasonCode: "structural_failed"},
			Errors:        []string{"invalid JSON: " + err.Error()},
		}, fmt.Errorf("invalid JSON: %w", err)
	}

	// Nested compact token.
	if tok, ok := raw["token"].(string); ok && strings.Count(tok, ".") == 2 {
		return v.validateCompactLevels(tok, 0, keys, require), nil
	}

	var token testsmcp.UCANToken
	if err := json.Unmarshal(data, &token); err != nil {
		return &DelegationValidationResult{
			IsValid:       false,
			Interface:     DelegationProofInterface,
			Structural:    LevelResult{Valid: false, Errors: []string{err.Error()}, ReasonCode: "invalid_json"},
			Cryptographic: LevelResult{Valid: false, Errors: []string{"structural_failed"}, ReasonCode: "structural_failed"},
			Errors:        []string{err.Error()},
		}, fmt.Errorf("invalid JSON: %w", err)
	}

	structuralErrs := []string{}
	if err := v.base.validate.Struct(token); err != nil {
		structuralErrs = append(structuralErrs, fmt.Sprintf("validation failed: %v", err))
	}
	if len(token.Capabilities) == 0 {
		structuralErrs = append(structuralErrs, "UCAN token must have at least one capability")
	}
	for i, cap := range token.Capabilities {
		if cap.With == "" {
			structuralErrs = append(structuralErrs, fmt.Sprintf("capability %d has empty 'with' field", i))
		}
		if cap.Can == "" {
			structuralErrs = append(structuralErrs, fmt.Sprintf("capability %d has empty 'can' field", i))
		}
	}

	cryptoErrs, cryptoReason, hasSig, cryptoOk := v.verifyObjectCrypto(raw, 0, keys)
	structuralOK := len(structuralErrs) == 0
	cryptoOK := structuralOK && cryptoOk
	isValid := structuralOK
	allErrs := append([]string{}, structuralErrs...)
	if hasSig && !cryptoOk {
		isValid = false
		allErrs = append(allErrs, cryptoErrs...)
	}
	if require && !cryptoOK {
		isValid = false
		if len(cryptoErrs) == 0 {
			cryptoErrs = []string{"signatures_required"}
			cryptoReason = "missing_signature"
		}
		allErrs = append(allErrs, cryptoErrs...)
	}
	if !hasSig {
		if len(cryptoErrs) == 0 {
			cryptoErrs = []string{"Token at index 0: missing signature"}
			cryptoReason = "missing_signature"
		}
		cryptoOK = false
	}

	res := &DelegationValidationResult{
		IsValid:    isValid,
		Interface:  DelegationProofInterface,
		Token:      &token,
		Errors:     uniqueStrings(allErrs),
		Structural: LevelResult{Valid: structuralOK, Errors: structuralErrs, ReasonCode: reasonIf(!structuralOK, "structural_invalid")},
		Cryptographic: LevelResult{
			Valid:      cryptoOK,
			Errors:     cryptoErrs,
			ReasonCode: reasonIf(!cryptoOK, firstNonEmpty(cryptoReason, "missing_signature")),
		},
		Metadata: map[string]interface{}{
			"canonical_algorithm": CanonicalAlgorithm,
			"require_signatures":  require,
		},
	}
	if structuralOK && cryptoOK {
		res.Conformance = "cryptographic"
	} else if structuralOK {
		res.Conformance = "structural"
	}
	if !structuralOK {
		return res, fmt.Errorf("%s", structuralErrs[0])
	}
	if hasSig && !cryptoOk {
		return res, fmt.Errorf("%s", cryptoErrs[0])
	}
	return res, nil
}

// VerifyDelegationProof cryptographically verifies a single token (DelegationProof@1).
// is_valid requires both structural and cryptographic success.
func (v *UCANValidator) VerifyDelegationProof(data []byte, issuerKeys map[string]interface{}) (*DelegationValidationResult, error) {
	res, _ := v.ValidateUCANTokenLevels(data, issuerKeys, true)
	// Force overall validity to require crypto.
	if res != nil {
		res.IsValid = res.Structural.Valid && res.Cryptographic.Valid
		if !res.IsValid && len(res.Errors) == 0 {
			res.Errors = append(res.Errors, "cryptographic_verification_failed")
		}
		if !res.IsValid {
			return res, fmt.Errorf("cryptographic verification failed")
		}
	}
	return res, nil
}

// ValidateDelegationChain validates a delegation chain.
//
// SPEC: UCAN-Delegation.md, chain MUST have root token and optional proofs
func (v *UCANValidator) ValidateDelegationChain(data []byte) (*testsmcp.DelegationChain, error) {
	res, err := v.ValidateDelegationChainLevels(data, nil, false)
	if err != nil {
		return nil, err
	}
	if !res.IsValid {
		if len(res.Errors) > 0 {
			return nil, fmt.Errorf("%s", res.Errors[0])
		}
		return nil, fmt.Errorf("validation failed")
	}
	return res.Chain, nil
}

// ValidateDelegationChainLevels validates a chain with dual-level reporting.
func (v *UCANValidator) ValidateDelegationChainLevels(data []byte, issuerKeys map[string]interface{}, requireSig bool) (*DelegationValidationResult, error) {
	var chain testsmcp.DelegationChain
	if err := json.Unmarshal(data, &chain); err != nil {
		return &DelegationValidationResult{
			IsValid:       false,
			Interface:     DelegationProofInterface,
			Structural:    LevelResult{Valid: false, Errors: []string{"invalid JSON: " + err.Error()}, ReasonCode: "invalid_json"},
			Cryptographic: LevelResult{Valid: false, Errors: []string{"structural_failed"}, ReasonCode: "structural_failed"},
			Errors:        []string{"invalid JSON: " + err.Error()},
		}, fmt.Errorf("invalid JSON: %w", err)
	}

	structuralErrs := []string{}
	if err := v.base.validate.Struct(chain); err != nil {
		structuralErrs = append(structuralErrs, fmt.Sprintf("validation failed: %v", err))
	}

	keys := mergeKeys(v.issuerPublicKeys, issuerKeys)
	require := v.requireSignatures || requireSig
	cryptoErrs := []string{}
	cryptoReason := ""
	allCryptoOK := true
	sawSig := false

	// Validate root
	rootJSON, _ := json.Marshal(chain.Root)
	rootRes, rootErr := v.ValidateUCANTokenLevels(rootJSON, keys, false)
	if rootErr != nil && rootRes != nil && !rootRes.Structural.Valid {
		structuralErrs = append(structuralErrs, "invalid root token: "+rootErr.Error())
	} else if rootErr != nil && rootRes != nil && rootRes.Structural.Valid && !rootRes.Cryptographic.Valid {
		// Crypto-only failure on root when signature present.
		if rootRes.Cryptographic.ReasonCode != "missing_signature" {
			cryptoErrs = append(cryptoErrs, rootRes.Cryptographic.Errors...)
			allCryptoOK = false
			sawSig = true
			cryptoReason = rootRes.Cryptographic.ReasonCode
		} else {
			cryptoErrs = append(cryptoErrs, rootRes.Cryptographic.Errors...)
			allCryptoOK = false
			cryptoReason = "missing_signature"
		}
	} else if rootRes != nil {
		if !rootRes.Cryptographic.Valid {
			allCryptoOK = false
			cryptoErrs = append(cryptoErrs, rootRes.Cryptographic.Errors...)
			cryptoReason = rootRes.Cryptographic.ReasonCode
			if rootRes.Cryptographic.ReasonCode != "missing_signature" {
				sawSig = true
			}
		}
	}

	for i, proof := range chain.Proofs {
		proofJSON, _ := json.Marshal(proof)
		proofRes, proofErr := v.ValidateUCANTokenLevels(proofJSON, keys, false)
		if proofErr != nil && proofRes != nil && !proofRes.Structural.Valid {
			structuralErrs = append(structuralErrs, fmt.Sprintf("invalid proof token %d: %v", i, proofErr))
		} else if proofRes != nil && !proofRes.Cryptographic.Valid {
			allCryptoOK = false
			cryptoErrs = append(cryptoErrs, proofRes.Cryptographic.Errors...)
			if cryptoReason == "" {
				cryptoReason = proofRes.Cryptographic.ReasonCode
			}
			if proofRes.Cryptographic.ReasonCode != "missing_signature" {
				sawSig = true
			}
		}
	}

	structuralOK := len(structuralErrs) == 0
	cryptoOK := structuralOK && allCryptoOK
	isValid := structuralOK
	allErrs := append([]string{}, structuralErrs...)
	if sawSig && !allCryptoOK {
		isValid = false
		allErrs = append(allErrs, cryptoErrs...)
	}
	if require && !cryptoOK {
		isValid = false
		allErrs = append(allErrs, cryptoErrs...)
	}

	res := &DelegationValidationResult{
		IsValid:   isValid,
		Interface: DelegationProofInterface,
		Chain:     &chain,
		Errors:    uniqueStrings(allErrs),
		Structural: LevelResult{
			Valid:      structuralOK,
			Errors:     structuralErrs,
			ReasonCode: reasonIf(!structuralOK, "structural_invalid"),
		},
		Cryptographic: LevelResult{
			Valid:      cryptoOK,
			Errors:     cryptoErrs,
			ReasonCode: reasonIf(!cryptoOK, firstNonEmpty(cryptoReason, "missing_signature")),
		},
		Metadata: map[string]interface{}{
			"canonical_algorithm": CanonicalAlgorithm,
			"require_signatures":  require,
		},
	}
	if structuralOK && cryptoOK {
		res.Conformance = "cryptographic"
	} else if structuralOK {
		res.Conformance = "structural"
	}
	if !structuralOK {
		return res, fmt.Errorf("%s", structuralErrs[0])
	}
	if sawSig && !allCryptoOK {
		return res, fmt.Errorf("%s", cryptoErrs[0])
	}
	return res, nil
}

// --- crypto helpers ---

func (v *UCANValidator) verifyObjectCrypto(raw map[string]interface{}, index int, keys map[string]interface{}) (errs []string, reason string, hasSig bool, ok bool) {
	sigRaw, hasSigField := raw["signature"]
	if !hasSigField {
		sigRaw, hasSigField = raw["sig"]
	}
	if !hasSigField || strings.TrimSpace(fmt.Sprint(sigRaw)) == "" {
		return []string{fmt.Sprintf("Token at index %d: missing signature", index)}, "missing_signature", false, false
	}
	hasSig = true

	header, _ := raw["header"].(map[string]interface{})
	if header == nil {
		header, _ = raw["protected"].(map[string]interface{})
	}
	alg, _ := raw["alg"].(string)
	kid, _ := raw["kid"].(string)
	if header != nil {
		if a, ok := header["alg"].(string); ok && a != "" {
			alg = a
		}
		if k, ok := header["kid"].(string); ok && k != "" {
			kid = k
		}
	}
	if sa, ok := raw["signature_alg"].(string); ok && alg == "" {
		alg = sa
	}
	if sa, ok := raw["signatureAlg"].(string); ok && alg == "" {
		alg = sa
	}

	if alg != "" {
		switch alg {
		case "none", "None", "NONE":
			return []string{fmt.Sprintf("Token at index %d: algorithm_or_version_downgrade", index)}, "algorithm_or_version_downgrade", true, false
		case SignatureAlgEdDSA, SignatureAlgEd25519, "ed25519":
			// ok (Ed25519 constant aliases SignatureAlgEd25519)
		default:
			return []string{fmt.Sprintf("Token at index %d: unsupported_signature_alg:%s", index, alg)}, "unsupported_signature_alg", true, false
		}
	}

	iss, _ := raw["iss"].(string)
	if iss == "" {
		iss, _ = raw["issuer"].(string)
	}
	if strings.TrimSpace(kid) == "" && !strings.HasPrefix(iss, "did:key:") {
		return []string{fmt.Sprintf("Token at index %d: missing_kid", index)}, "missing_kid", true, false
	}

	sig, err := decodeSignature(sigRaw)
	if err != nil || len(sig) != ed25519.SignatureSize {
		return []string{fmt.Sprintf("Token at index %d: invalid_signature_encoding", index)}, "invalid_signature_encoding", true, false
	}

	pub, err := resolvePublicKey(raw, keys, kid)
	if err != nil || len(pub) != ed25519.PublicKeySize {
		return []string{fmt.Sprintf("Token at index %d: verification_key_unavailable", index)}, "verification_key_unavailable", true, false
	}

	var message []byte
	if header != nil {
		if payload, ok := raw["payload"].(map[string]interface{}); ok {
			message, err = compactSigningInput(header, payload)
		} else {
			message, err = compactSigningInput(header, signingObject(raw))
		}
	} else {
		message, err = canonicalSigningBytes(raw)
	}
	if err != nil {
		return []string{fmt.Sprintf("Token at index %d: canonicalization_failed", index)}, "canonicalization_failed", true, false
	}

	if !ed25519.Verify(ed25519.PublicKey(pub), message, sig) {
		return []string{fmt.Sprintf("Token at index %d: invalid_signature", index)}, "invalid_signature", true, false
	}
	return nil, "", true, true
}

func (v *UCANValidator) validateCompactLevels(token string, index int, keys map[string]interface{}, require bool) *DelegationValidationResult {
	structuralErrs := []string{}
	cryptoErrs := []string{}
	parts := strings.Split(token, ".")
	if len(parts) != 3 || parts[0] == "" || parts[1] == "" || parts[2] == "" {
		structuralErrs = append(structuralErrs,
			fmt.Sprintf("Token at index %d missing required field: att", index),
			fmt.Sprintf("Token at index %d missing required field: exp", index),
		)
		cryptoErrs = append(cryptoErrs, fmt.Sprintf("Token at index %d: unsigned_or_malformed_token", index))
		return levelResult(false, structuralErrs, cryptoErrs, "unsigned_or_malformed_token", false)
	}

	headerBytes, err := b64urlDecode(parts[0])
	if err != nil {
		return levelResult(false, []string{fmt.Sprintf("Token at index %d missing required field: iss", index)},
			[]string{fmt.Sprintf("Token at index %d: malformed_token", index)}, "malformed_token", true)
	}
	payloadBytes, err := b64urlDecode(parts[1])
	if err != nil {
		return levelResult(false, []string{fmt.Sprintf("Token at index %d missing required field: iss", index)},
			[]string{fmt.Sprintf("Token at index %d: malformed_token", index)}, "malformed_token", true)
	}
	sig, err := b64urlDecode(parts[2])
	if err != nil || len(sig) != ed25519.SignatureSize {
		return levelResult(false, nil,
			[]string{fmt.Sprintf("Token at index %d: invalid_signature_encoding", index)}, "invalid_signature_encoding", true)
	}

	var header map[string]interface{}
	var payload map[string]interface{}
	if err := json.Unmarshal(headerBytes, &header); err != nil {
		return levelResult(false, []string{fmt.Sprintf("Token at index %d missing required field: iss", index)},
			[]string{fmt.Sprintf("Token at index %d: malformed_token", index)}, "malformed_token", true)
	}
	if err := json.Unmarshal(payloadBytes, &payload); err != nil {
		return levelResult(false, []string{fmt.Sprintf("Token at index %d missing required field: iss", index)},
			[]string{fmt.Sprintf("Token at index %d: malformed_token", index)}, "malformed_token", true)
	}

	for _, field := range []string{"iss", "aud", "att", "exp"} {
		if _, ok := payload[field]; !ok {
			structuralErrs = append(structuralErrs, fmt.Sprintf("Token at index %d missing required field: %s", index, field))
		}
	}
	if att, ok := payload["att"]; ok {
		if _, isArr := att.([]interface{}); !isArr {
			structuralErrs = append(structuralErrs, fmt.Sprintf("Token at index %d: 'att' must be a list", index))
		}
	}

	if !headerKeysExact(header) || header["alg"] != SignatureAlgEdDSA || header["typ"] != "UCAN" {
		// v must be numeric 1
		cryptoErrs = append(cryptoErrs, fmt.Sprintf("Token at index %d: algorithm_or_version_downgrade", index))
		return levelResult(len(structuralErrs) == 0, structuralErrs, cryptoErrs, "algorithm_or_version_downgrade", true)
	}
	switch vv := header["v"].(type) {
	case float64:
		if vv != 1 {
			cryptoErrs = append(cryptoErrs, fmt.Sprintf("Token at index %d: algorithm_or_version_downgrade", index))
			return levelResult(len(structuralErrs) == 0, structuralErrs, cryptoErrs, "algorithm_or_version_downgrade", true)
		}
	case int:
		if vv != 1 {
			cryptoErrs = append(cryptoErrs, fmt.Sprintf("Token at index %d: algorithm_or_version_downgrade", index))
			return levelResult(len(structuralErrs) == 0, structuralErrs, cryptoErrs, "algorithm_or_version_downgrade", true)
		}
	default:
		cryptoErrs = append(cryptoErrs, fmt.Sprintf("Token at index %d: algorithm_or_version_downgrade", index))
		return levelResult(len(structuralErrs) == 0, structuralErrs, cryptoErrs, "algorithm_or_version_downgrade", true)
	}
	if strings.TrimSpace(fmt.Sprint(header["kid"])) == "" {
		cryptoErrs = append(cryptoErrs, fmt.Sprintf("Token at index %d: missing_kid", index))
		return levelResult(len(structuralErrs) == 0, structuralErrs, cryptoErrs, "missing_kid", true)
	}

	// Canonical header/payload segments.
	hCanon, err := testsmcp.Canonicalize(header)
	if err != nil || b64urlEncode(hCanon) != parts[0] {
		cryptoErrs = append(cryptoErrs, fmt.Sprintf("Token at index %d: noncanonical_header", index))
		return levelResult(len(structuralErrs) == 0, structuralErrs, cryptoErrs, "noncanonical_header", true)
	}
	pCanon, err := testsmcp.Canonicalize(payload)
	if err != nil || b64urlEncode(pCanon) != parts[1] {
		cryptoErrs = append(cryptoErrs, fmt.Sprintf("Token at index %d: noncanonical_payload", index))
		return levelResult(len(structuralErrs) == 0, structuralErrs, cryptoErrs, "noncanonical_payload", true)
	}

	iss, _ := payload["iss"].(string)
	pub, err := resolvePublicKey(map[string]interface{}{"iss": iss}, keys, fmt.Sprint(header["kid"]))
	if err != nil {
		// try did:key
		pub, err = ed25519PublicKeyFromDIDKey(iss)
	}
	if err != nil || len(pub) != ed25519.PublicKeySize {
		cryptoErrs = append(cryptoErrs, fmt.Sprintf("Token at index %d: verification_key_unavailable", index))
		return levelResult(len(structuralErrs) == 0, structuralErrs, cryptoErrs, "verification_key_unavailable", true)
	}

	message := []byte(parts[0] + "." + parts[1])
	if !ed25519.Verify(ed25519.PublicKey(pub), message, sig) {
		cryptoErrs = append(cryptoErrs, fmt.Sprintf("Token at index %d: invalid_signature", index))
		return levelResult(len(structuralErrs) == 0, structuralErrs, cryptoErrs, "invalid_signature", true)
	}

	structuralOK := len(structuralErrs) == 0
	cryptoOK := structuralOK
	isValid := structuralOK
	if require && !cryptoOK {
		isValid = false
	}
	_ = require
	res := &DelegationValidationResult{
		IsValid:       isValid,
		Interface:     DelegationProofInterface,
		Errors:        structuralErrs,
		Structural:    LevelResult{Valid: structuralOK, Errors: structuralErrs, ReasonCode: reasonIf(!structuralOK, "structural_invalid")},
		Cryptographic: LevelResult{Valid: cryptoOK, Errors: nil, ReasonCode: ""},
		Metadata:      map[string]interface{}{"canonical_algorithm": CanonicalAlgorithm},
	}
	if structuralOK && cryptoOK {
		res.Conformance = "cryptographic"
	} else if structuralOK {
		res.Conformance = "structural"
	}
	return res
}

func levelResult(structuralOK bool, structuralErrs, cryptoErrs []string, cryptoReason string, hasSig bool) *DelegationValidationResult {
	isValid := structuralOK
	if hasSig && cryptoReason != "" && cryptoReason != "missing_signature" {
		isValid = false
	}
	all := append([]string{}, structuralErrs...)
	if !isValid {
		all = append(all, cryptoErrs...)
	}
	res := &DelegationValidationResult{
		IsValid:    isValid,
		Interface:  DelegationProofInterface,
		Errors:     uniqueStrings(all),
		Structural: LevelResult{Valid: structuralOK, Errors: structuralErrs, ReasonCode: reasonIf(!structuralOK, "structural_invalid")},
		Cryptographic: LevelResult{
			Valid:      false,
			Errors:     cryptoErrs,
			ReasonCode: cryptoReason,
		},
		Metadata: map[string]interface{}{"canonical_algorithm": CanonicalAlgorithm},
	}
	if structuralOK {
		res.Conformance = "structural"
	}
	return res
}

func signingObject(raw map[string]interface{}) map[string]interface{} {
	if payload, ok := raw["payload"].(map[string]interface{}); ok {
		out := map[string]interface{}{}
		for k, v := range payload {
			if !isSigMeta(k) {
				out[k] = v
			}
		}
		return out
	}
	out := map[string]interface{}{}
	for k, v := range raw {
		if !isSigMeta(k) && k != "token" {
			out[k] = v
		}
	}
	return out
}

func isSigMeta(k string) bool {
	switch k {
	case "signature", "sig", "signatures", "public_key", "publicKey", "public_key_b64",
		"issuer_public_key", "header", "protected", "alg", "kid", "signature_alg", "signatureAlg":
		return true
	default:
		return false
	}
}

func canonicalSigningBytes(raw map[string]interface{}) ([]byte, error) {
	return testsmcp.Canonicalize(signingObject(raw))
}

func compactSigningInput(header, payload map[string]interface{}) ([]byte, error) {
	h, err := testsmcp.Canonicalize(header)
	if err != nil {
		return nil, err
	}
	p, err := testsmcp.Canonicalize(payload)
	if err != nil {
		return nil, err
	}
	return []byte(b64urlEncode(h) + "." + b64urlEncode(p)), nil
}

func b64urlEncode(raw []byte) string {
	return base64.RawURLEncoding.EncodeToString(raw)
}

func b64urlDecode(s string) ([]byte, error) {
	text := strings.TrimSpace(s)
	if text == "" {
		return nil, fmt.Errorf("empty_base64url")
	}
	for _, ch := range text {
		if !((ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9') || ch == '-' || ch == '_') {
			return nil, fmt.Errorf("invalid_base64url")
		}
	}
	decoded, err := base64.RawURLEncoding.DecodeString(text)
	if err != nil {
		return nil, err
	}
	if b64urlEncode(decoded) != text {
		return nil, fmt.Errorf("noncanonical_base64url")
	}
	return decoded, nil
}

func decodeSignature(value interface{}) ([]byte, error) {
	switch v := value.(type) {
	case []byte:
		if len(v) == ed25519.SignatureSize {
			return v, nil
		}
		return nil, fmt.Errorf("invalid_signature_length")
	case string:
		text := strings.TrimSpace(v)
		if strings.HasPrefix(text, "ed25519:") {
			text = strings.TrimSpace(strings.TrimPrefix(text, "ed25519:"))
		} else if strings.HasPrefix(text, "ed25519-hex:") || strings.HasPrefix(text, "hex:") {
			parts := strings.SplitN(text, ":", 2)
			raw, err := hex.DecodeString(strings.TrimSpace(parts[1]))
			if err != nil || len(raw) != ed25519.SignatureSize {
				return nil, fmt.Errorf("invalid_signature_encoding")
			}
			return raw, nil
		}
		if len(text) == 128 {
			raw, err := hex.DecodeString(text)
			if err == nil && len(raw) == ed25519.SignatureSize {
				return raw, nil
			}
		}
		return b64urlDecode(text)
	default:
		return nil, fmt.Errorf("invalid_signature_type")
	}
}

func decodePublicKey(value interface{}) ([]byte, error) {
	switch v := value.(type) {
	case []byte:
		if len(v) == ed25519.PublicKeySize {
			return v, nil
		}
		return nil, fmt.Errorf("invalid_public_key_length")
	case map[string]interface{}:
		alg, _ := v["alg"].(string)
		if alg == "" {
			alg, _ = v["algorithm"].(string)
		}
		alg = strings.ToLower(strings.TrimSpace(alg))
		if alg != "" && alg != "ed25519" && alg != "eddsa" {
			return nil, fmt.Errorf("unsupported_alg")
		}
		for _, key := range []string{"public_key", "public_key_b64", "public_key_base64", "publicKey", "key", "did_key", "did"} {
			if val, ok := v[key]; ok {
				return decodePublicKey(val)
			}
		}
		if hexKey, ok := v["public_key_hex"].(string); ok {
			return decodePublicKey(hexKey)
		}
		return nil, fmt.Errorf("missing_public_key")
	case string:
		text := strings.TrimSpace(v)
		if strings.HasPrefix(text, "did:key:") {
			return ed25519PublicKeyFromDIDKey(text)
		}
		if strings.HasPrefix(text, "ed25519-pub:") {
			text = strings.TrimSpace(strings.TrimPrefix(text, "ed25519-pub:"))
		}
		if len(text) == 64 {
			if raw, err := hex.DecodeString(text); err == nil && len(raw) == ed25519.PublicKeySize {
				return raw, nil
			}
		}
		if raw, err := b64urlDecode(text); err == nil && len(raw) == ed25519.PublicKeySize {
			return raw, nil
		}
		if raw, err := base64.StdEncoding.DecodeString(text); err == nil && len(raw) == ed25519.PublicKeySize {
			return raw, nil
		}
		return nil, fmt.Errorf("invalid_public_key")
	default:
		return nil, fmt.Errorf("invalid_public_key_type")
	}
}

func resolvePublicKey(raw map[string]interface{}, keys map[string]interface{}, kid string) ([]byte, error) {
	for _, keyName := range []string{"public_key", "publicKey", "issuer_public_key", "public_key_b64"} {
		if val, ok := raw[keyName]; ok {
			return decodePublicKey(val)
		}
	}
	iss, _ := raw["iss"].(string)
	if iss == "" {
		iss, _ = raw["issuer"].(string)
	}
	if iss != "" {
		if entry, ok := keys[iss]; ok {
			if m, ok := entry.(map[string]interface{}); ok && kid != "" {
				if _, hasPK := m["public_key"]; !hasPK {
					if kidVal, ok := m[kid]; ok {
						if pub, err := decodePublicKey(kidVal); err == nil {
							return pub, nil
						}
					}
				}
			}
			if pub, err := decodePublicKey(entry); err == nil {
				return pub, nil
			}
		}
		if pub, err := ed25519PublicKeyFromDIDKey(iss); err == nil {
			return pub, nil
		}
	}
	return nil, fmt.Errorf("verification_key_unavailable")
}

const b58Alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

func ed25519PublicKeyFromDIDKey(did string) ([]byte, error) {
	if !strings.HasPrefix(did, "did:key:") {
		return nil, fmt.Errorf("not_did_key")
	}
	mb := strings.TrimPrefix(did, "did:key:")
	if !strings.HasPrefix(mb, "z") {
		return nil, fmt.Errorf("not_base58btc")
	}
	decoded, err := base58btcDecode(mb[1:])
	if err != nil {
		return nil, err
	}
	if len(decoded) >= 34 && decoded[0] == 0xed && decoded[1] == 0x01 {
		return decoded[2:34], nil
	}
	return nil, fmt.Errorf("not_ed25519_did_key")
}

func base58btcDecode(value string) ([]byte, error) {
	if value == "" {
		return nil, nil
	}
	acc := big.NewInt(0)
	base := big.NewInt(58)
	for _, ch := range value {
		idx := strings.IndexRune(b58Alphabet, ch)
		if idx < 0 {
			return nil, fmt.Errorf("invalid_base58btc")
		}
		acc.Mul(acc, base)
		acc.Add(acc, big.NewInt(int64(idx)))
	}
	raw := acc.Bytes()
	zeros := 0
	for _, ch := range value {
		if ch != '1' {
			break
		}
		zeros++
	}
	out := make([]byte, zeros+len(raw))
	copy(out[zeros:], raw)
	return out, nil
}

func headerKeysExact(header map[string]interface{}) bool {
	if len(header) != 4 {
		return false
	}
	for _, k := range []string{"alg", "kid", "typ", "v"} {
		if _, ok := header[k]; !ok {
			return false
		}
	}
	return true
}

func mergeKeys(a, b map[string]interface{}) map[string]interface{} {
	out := map[string]interface{}{}
	for k, v := range a {
		out[k] = v
	}
	for k, v := range b {
		out[k] = v
	}
	return out
}

func uniqueStrings(in []string) []string {
	seen := map[string]struct{}{}
	out := []string{}
	for _, s := range in {
		if s == "" {
			continue
		}
		if _, ok := seen[s]; ok {
			continue
		}
		seen[s] = struct{}{}
		out = append(out, s)
	}
	return out
}

func reasonIf(cond bool, code string) string {
	if cond {
		return code
	}
	return ""
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if v != "" {
			return v
		}
	}
	return ""
}
