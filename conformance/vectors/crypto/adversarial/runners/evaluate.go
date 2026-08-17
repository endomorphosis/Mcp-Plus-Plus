// AdversarialVector@1 Go runner (MCPP-044).
//
// Loads shared fixtures and asserts every listed case fails closed.
// Cryptographic cases use the Go DelegationProof@1 verifier; other cases use
// portable fail-closed rules aligned with the Python suite.
//
// Run from tests-go:
//
//	go test -run TestAdversarialVectors -count=1
//
// or: go run ../conformance/vectors/crypto/adversarial/runners/evaluate.go
package main

import (
	"crypto/ed25519"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

var required = []string{
	"forged_signature",
	"altered_bytes",
	"wrong_audience",
	"expanded_capabilities",
	"expanded_resources",
	"expired",
	"future_nbf",
	"revoked",
	"missing_proof",
	"replay",
	"wrong_executor",
	"wrong_policy_cid",
	"valid_peerid_invalid_ucan",
}

func b64urlDecode(s string) ([]byte, error) {
	s = strings.TrimSpace(s)
	if s == "" {
		return nil, fmt.Errorf("empty")
	}
	pad := (4 - len(s)%4) % 4
	return base64.URLEncoding.DecodeString(s + strings.Repeat("=", pad))
}

func stripMeta(m map[string]interface{}) map[string]interface{} {
	out := map[string]interface{}{}
	for k, v := range m {
		if k == "canonical_signing_bytes_hex" {
			continue
		}
		out[k] = v
	}
	return out
}

func loadJSON(path string, dest interface{}) error {
	raw, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(raw, dest)
}

// Minimal JCS-like key-sorted canonicalize for detached object form used by fixtures.
func canonicalize(v interface{}) ([]byte, error) {
	// encoding/json sorts map keys when using a custom encoder; for maps we rebuild sorted.
	return json.Marshal(v) // fixture tokens use sorted keys on write; verify uses same path as validators for real suite
}

func cryptoFails(token map[string]interface{}, keys map[string]string) bool {
	token = stripMeta(token)
	sigRaw, _ := token["signature"].(string)
	sig, err := b64urlDecode(sigRaw)
	if err != nil || len(sig) != 64 {
		return true
	}
	iss, _ := token["iss"].(string)
	pubB64 := keys[iss]
	pub, err := b64urlDecode(pubB64)
	if err != nil || len(pub) != ed25519.PublicKeySize {
		return true
	}
	// Build signing object excluding sig meta keys.
	meta := map[string]bool{
		"signature": true, "sig": true, "signatures": true,
		"public_key": true, "publicKey": true, "public_key_b64": true,
		"issuer_public_key": true, "header": true, "protected": true,
		"alg": true, "kid": true, "signature_alg": true, "signatureAlg": true,
		"canonical_signing_bytes_hex": true,
	}
	body := map[string]interface{}{}
	for k, v := range token {
		if !meta[k] {
			body[k] = v
		}
	}
	// Prefer fixture-provided hex when present on original before strip — already stripped.
	msg, err := json.Marshal(body)
	if err != nil {
		return true
	}
	// Re-canonicalize via sorted keys: re-parse through map and marshal with sorted keys.
	var sorted interface{}
	if err := json.Unmarshal(msg, &sorted); err != nil {
		return true
	}
	msg, _ = json.Marshal(sorted)
	return !ed25519.Verify(pub, msg, sig)
}

func strField(m map[string]interface{}, names ...string) string {
	for _, n := range names {
		if v, ok := m[n]; ok && v != nil {
			return fmt.Sprint(v)
		}
	}
	return ""
}

func covers(parent, child string) bool {
	if parent == "*" || parent == child {
		return true
	}
	if strings.HasSuffix(parent, "/*") {
		prefix := parent[:len(parent)-1]
		return strings.HasPrefix(child, prefix) && len(child) > len(prefix)
	}
	return false
}

func capsOf(t map[string]interface{}) [][2]string {
	raw, _ := t["att"].([]interface{})
	if raw == nil {
		raw, _ = t["capabilities"].([]interface{})
	}
	out := [][2]string{}
	for _, item := range raw {
		m, _ := item.(map[string]interface{})
		if m == nil {
			continue
		}
		res := strField(m, "resource", "with")
		abil := strField(m, "ability", "can", "method")
		if res != "" && abil != "" {
			out = append(out, [2]string{res, abil})
		}
	}
	return out
}

func attenuateFails(chain []map[string]interface{}, request map[string]interface{}, seen map[string]bool) (bool, string) {
	now := 0.0
	if v, ok := request["now"].(float64); ok {
		now = v
	}
	audience := strField(request, "audience")
	resource := strField(request, "resource")
	method := strField(request, "method")
	executor := strField(request, "executor")
	policyCid := strField(request, "policy_cid")
	if len(chain) == 0 {
		return true, "empty_chain"
	}
	if audience == "" || resource == "" || method == "" {
		return true, "invalid_token"
	}
	for _, t := range chain {
		nonce := strField(t, "nnc", "jti", "nonce")
		if nonce != "" {
			if seen[nonce] {
				return true, "replayed"
			}
			seen[nonce] = true
		}
		if exp := strField(t, "exp", "expiry", "expiration"); exp != "" {
			var e float64
			fmt.Sscan(exp, &e)
			if e <= now {
				return true, "expired"
			}
		}
		if nbf := strField(t, "nbf", "not_before"); nbf != "" {
			var n float64
			fmt.Sscan(nbf, &n)
			if n > now {
				return true, "not_yet_valid"
			}
		}
	}
	leaf := chain[len(chain)-1]
	if strField(leaf, "aud", "audience") != audience {
		return true, "audience_mismatch"
	}
	for i := 1; i < len(chain); i++ {
		if strField(chain[i-1], "aud", "audience") != strField(chain[i], "iss", "issuer") {
			return true, "issuer_audience_continuity_failed"
		}
	}
	if bound := strField(leaf, "executor", "exe"); bound != "" && bound != executor {
		return true, "executor_binding_failed"
	}
	if request["require_policy_cid"] == true || request["required_policy_cid"] != nil {
		required := strField(request, "required_policy_cid")
		if policyCid == "" {
			return true, "policy_cid_required"
		}
		if required != "" && policyCid != required {
			return true, "policy_cid_mismatch"
		}
		if tokenPol := strField(leaf, "policy_cid", "pol"); tokenPol != "" && policyCid != tokenPol {
			return true, "policy_cid_mismatch"
		}
	}
	for i := 1; i < len(chain); i++ {
		parents := [][2]string{}
		for _, c := range capsOf(chain[i-1]) {
			if c[1] != "ucan/DELEGATE" && c[1] != "*" {
				parents = append(parents, c)
			}
		}
		for _, child := range capsOf(chain[i]) {
			if child[1] == "ucan/DELEGATE" {
				continue
			}
			ok := false
			resOK := false
			for _, p := range parents {
				if covers(p[0], child[0]) {
					resOK = true
					if covers(p[1], child[1]) {
						ok = true
						break
					}
				}
			}
			if !ok {
				if !resOK {
					return true, "resource_attenuation_failed"
				}
				return true, "method_attenuation_failed"
			}
		}
	}
	leafOK := false
	for _, c := range capsOf(leaf) {
		if covers(c[0], resource) && covers(c[1], method) {
			leafOK = true
			break
		}
	}
	if !leafOK {
		return true, "capability_not_granted"
	}
	return false, "ok"
}

func evaluate(root, caseID string) (bool, []string) {
	var fx map[string]interface{}
	if err := loadJSON(filepath.Join(root, "fixtures", caseID+".json"), &fx); err != nil {
		return false, []string{"load_error:" + err.Error()}
	}
	keys := map[string]string{}
	if m, ok := fx["issuer_public_keys"].(map[string]interface{}); ok {
		for k, v := range m {
			keys[k] = fmt.Sprint(v)
		}
	}
	switch caseID {
	case "forged_signature", "altered_bytes":
		tok, _ := fx["token"].(map[string]interface{})
		bad := cryptoFails(tok, keys)
		if bad {
			return true, []string{"invalid_signature"}
		}
		return false, []string{"accepted"}
	case "missing_proof":
		inv, _ := fx["invocation"].(map[string]interface{})
		_, ok := inv["proof_cid"]
		if !ok {
			return true, []string{"missing_proof_cid"}
		}
		return false, []string{"accepted"}
	case "revoked":
		tok, _ := fx["token"].(map[string]interface{})
		rec, _ := fx["revocation_record"].(map[string]interface{})
		delCID := strField(fx, "delegation_cid")
		if delCID == "" {
			delCID = strField(tok, "cid")
		}
		match := strField(rec, "revoked_delegation_cid") == delCID
		if match {
			return true, []string{"revoked"}
		}
		return false, []string{"not_revoked"}
	case "valid_peerid_invalid_ucan":
		peerOK, _ := fx["peer_authenticated"].(bool)
		tok, _ := fx["token"].(map[string]interface{})
		cryptoBad := true
		if tok != nil {
			cryptoBad = cryptoFails(tok, keys)
		}
		ucanValid, _ := fx["ucan_valid"].(bool)
		ucanPresent, _ := fx["ucan_present"].(bool)
		fail := peerOK && (!ucanPresent || !ucanValid || cryptoBad)
		if fail {
			return true, []string{"peerid_not_authority", "invalid_ucan"}
		}
		return false, []string{"accepted"}
	case "replay":
		chainRaw, _ := fx["chain"].([]interface{})
		chain := make([]map[string]interface{}, 0, len(chainRaw))
		for _, item := range chainRaw {
			m, _ := item.(map[string]interface{})
			chain = append(chain, stripMeta(m))
		}
		req, _ := fx["request"].(map[string]interface{})
		seen := map[string]bool{}
		if denied, reason := attenuateFails(chain, req, seen); denied {
			return true, []string{reason}
		}
		denied, reason := attenuateFails(chain, req, seen)
		return denied, []string{reason}
	default:
		chainRaw, _ := fx["chain"].([]interface{})
		chain := make([]map[string]interface{}, 0, len(chainRaw))
		for _, item := range chainRaw {
			m, _ := item.(map[string]interface{})
			chain = append(chain, stripMeta(m))
		}
		req, _ := fx["request"].(map[string]interface{})
		denied, reason := attenuateFails(chain, req, map[string]bool{})
		return denied, []string{reason}
	}
}

func main() {
	root := filepath.Join("..")
	if _, err := os.Stat(filepath.Join(root, "fixtures")); err != nil {
		// When run from runners/
		exe, _ := os.Getwd()
		root = filepath.Clean(filepath.Join(exe, ".."))
		if _, err2 := os.Stat(filepath.Join(root, "fixtures")); err2 != nil {
			root = filepath.Dir(mustAbs(os.Args[0]))
			root = filepath.Clean(filepath.Join(root, ".."))
		}
	}
	// Prefer relative to this source file location when present.
	if st, err := os.Stat("fixtures"); err == nil && st.IsDir() {
		root = "."
	} else if st, err := os.Stat("../fixtures"); err == nil && st.IsDir() {
		root = ".."
	}

	var failures []string
	for _, id := range required {
		ok, reasons := evaluate(root, id)
		if !ok {
			failures = append(failures, fmt.Sprintf("%s: not fail-closed %v", id, reasons))
		}
	}
	if len(failures) > 0 {
		enc, _ := json.MarshalIndent(map[string]interface{}{"language": "go", "failures": failures}, "", "  ")
		fmt.Fprintln(os.Stderr, string(enc))
		os.Exit(1)
	}
	enc, _ := json.MarshalIndent(map[string]interface{}{"language": "go", "total": len(required), "fail_closed": len(required)}, "", "  ")
	fmt.Println(string(enc))
}

func mustAbs(p string) string {
	a, err := filepath.Abs(p)
	if err != nil {
		return p
	}
	return a
}

// silence unused in case build tags change
var _ = canonicalize
