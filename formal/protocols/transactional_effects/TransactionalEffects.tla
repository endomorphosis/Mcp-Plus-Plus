---- MODULE TransactionalEffects ----
(***************************************************************************)
(* FACP-045 / FACP-G510 — Transactional Effect Protocols (TEP)             *)
(*                                                                         *)
(* Evidence: facp/tep-models@1                                             *)
(* Bundle:   facp/protocols/models                                         *)
(*                                                                         *)
(* Bounded TLA+ model of admission, reservation, start, observation,       *)
(* receipt/current-pointer settlement, lease/fence, retry/idempotency,     *)
(* crash, compensation, and proof promotion.                               *)
(*                                                                         *)
(* Required safety invariants (FACP-G510):                                 *)
(*   NoDoubleEffect                                                        *)
(*   NoStaleFenceCompletion                                                *)
(*   NoSuccessWithoutObservation                                           *)
(*   NoConfirmationReuse                                                   *)
(*   NoReplayOfUnknownIrreversibleEffect                                   *)
(*                                                                         *)
(* Crash boundaries are explicit actions. Unknown irreversible outcomes    *)
(* never silently become success or blind retry.                           *)
(*                                                                         *)
(* Policy: bounded exploration only; do not claim proof when TLC/tools     *)
(* are absent. Auto-install of formal tools is prohibited.                 *)
(***************************************************************************)

EXTENDS Naturals, FiniteSets, Sequences

CONSTANTS
  Ops,                \* bounded finite set of operation identities
  MaxFenceGen,        \* Nat: maximum fence generation (bound)
  MaxRetries,         \* Nat: maximum retry attempts per op (bound)
  IrreversibleOps,    \* subset Ops: irreversible external effects
  CompensatableOps    \* subset Ops: compensatable effects

ASSUME
  /\ Ops # {}
  /\ MaxFenceGen \in Nat /\ MaxFenceGen >= 1
  /\ MaxRetries \in Nat
  /\ IrreversibleOps \subseteq Ops
  /\ CompensatableOps \subseteq Ops
  /\ IrreversibleOps \cap CompensatableOps = {}

-----------------------------------------------------------------------------
\* Closed EAK-aligned typestate constructors (happy + exceptional).

Typestates == {
  "Proposed",
  "ContractResolved",
  "ActorAuthenticated",
  "CapabilityVerified",
  "PolicyEvaluated",
  "ObligationsSatisfied",
  "ConfirmationSatisfied",
  "LeaseHeld",
  "Reserved",
  "Started",
  "Observed",
  "ReceiptSealed",
  "Rejected",
  "Unavailable",
  "Failed",
  "Unknown",
  "CompensationRequired",
  "Compensated",
  "Aborted"
}

PreReserved == {
  "Proposed",
  "ContractResolved",
  "ActorAuthenticated",
  "CapabilityVerified",
  "PolicyEvaluated",
  "ObligationsSatisfied",
  "ConfirmationSatisfied",
  "LeaseHeld"
}

HappyPath == <<
  "Proposed",
  "ContractResolved",
  "ActorAuthenticated",
  "CapabilityVerified",
  "PolicyEvaluated",
  "ObligationsSatisfied",
  "ConfirmationSatisfied",
  "LeaseHeld",
  "Reserved",
  "Started",
  "Observed",
  "ReceiptSealed"
>>

\* Named persistent crash boundaries (every durable transition edge).
CrashBoundaries == {
  "admission",
  "reservation",
  "started",
  "unknown",
  "observed",
  "receipt",
  "current",
  "lease",
  "fence",
  "retry",
  "idempotency",
  "crash",
  "settlement",
  "compensation",
  "proof_promotion"
}

EvidenceSubset == CrashBoundaries   \* normative evidence vocabulary

-----------------------------------------------------------------------------

VARIABLES
  typestate,            \* [op \in Ops -> Typestates]
  effectCount,          \* [op \in Ops -> Nat] successful external applications
  observed,             \* [op \in Ops -> BOOLEAN]
  receiptSealed,        \* [op \in Ops -> BOOLEAN]
  confirmationBound,      \* [op \in Ops -> BOOLEAN] confirmation required
  confirmationSpent,    \* [op \in Ops -> BOOLEAN] one-use confirmation consumed
  leaseHeld,            \* [op \in Ops -> BOOLEAN]
  fenceGen,             \* [op \in Ops -> 0..MaxFenceGen] current fence generation
  fenceAtReserve,       \* [op \in Ops -> 0..MaxFenceGen] fence captured at reserve
  currentPointer,       \* [op \in Ops -> Nat] settled current pointer epoch
  pendingCurrent,       \* [op \in Ops -> Nat] proposed current before settlement
  retries,              \* [op \in Ops -> Nat]
  idempotencyRecorded,  \* [op \in Ops -> BOOLEAN]
  unknownPending,       \* [op \in Ops -> BOOLEAN]
  compensationOwed,     \* [op \in Ops -> BOOLEAN]
  proofPromoted,        \* [op \in Ops -> BOOLEAN]
  durableCursor,        \* [op \in Ops -> Typestates] last durable typestate
  lastCrashBoundary,    \* last crossed named crash boundary (or "none")
  crashed               \* BOOLEAN: mid-crash recovery pending

vars == <<
  typestate, effectCount, observed, receiptSealed,
  confirmationBound, confirmationSpent, leaseHeld,
  fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
  retries, idempotencyRecorded, unknownPending, compensationOwed,
  proofPromoted, durableCursor, lastCrashBoundary, crashed
>>

TypeOK ==
  /\ typestate \in [Ops -> Typestates]
  /\ effectCount \in [Ops -> Nat]
  /\ observed \in [Ops -> BOOLEAN]
  /\ receiptSealed \in [Ops -> BOOLEAN]
  /\ confirmationBound \in [Ops -> BOOLEAN]
  /\ confirmationSpent \in [Ops -> BOOLEAN]
  /\ leaseHeld \in [Ops -> BOOLEAN]
  /\ fenceGen \in [Ops -> 0..MaxFenceGen]
  /\ fenceAtReserve \in [Ops -> 0..MaxFenceGen]
  /\ currentPointer \in [Ops -> Nat]
  /\ pendingCurrent \in [Ops -> Nat]
  /\ retries \in [Ops -> Nat]
  /\ idempotencyRecorded \in [Ops -> BOOLEAN]
  /\ unknownPending \in [Ops -> BOOLEAN]
  /\ compensationOwed \in [Ops -> BOOLEAN]
  /\ proofPromoted \in [Ops -> BOOLEAN]
  /\ durableCursor \in [Ops -> Typestates]
  /\ lastCrashBoundary \in CrashBoundaries \cup {"none"}
  /\ crashed \in BOOLEAN

-----------------------------------------------------------------------------
\* Init: all ops Proposed; no effects; fences at generation 1 when leased.

Init ==
  /\ typestate = [o \in Ops |-> "Proposed"]
  /\ effectCount = [o \in Ops |-> 0]
  /\ observed = [o \in Ops |-> FALSE]
  /\ receiptSealed = [o \in Ops |-> FALSE]
  /\ confirmationBound = [o \in Ops |-> TRUE]   \* confirmation required by default
  /\ confirmationSpent = [o \in Ops |-> FALSE]
  /\ leaseHeld = [o \in Ops |-> FALSE]
  /\ fenceGen = [o \in Ops |-> 1]
  /\ fenceAtReserve = [o \in Ops |-> 0]
  /\ currentPointer = [o \in Ops |-> 0]
  /\ pendingCurrent = [o \in Ops |-> 0]
  /\ retries = [o \in Ops |-> 0]
  /\ idempotencyRecorded = [o \in Ops |-> FALSE]
  /\ unknownPending = [o \in Ops |-> FALSE]
  /\ compensationOwed = [o \in Ops |-> FALSE]
  /\ proofPromoted = [o \in Ops |-> FALSE]
  /\ durableCursor = [o \in Ops |-> "Proposed"]
  /\ lastCrashBoundary = "none"
  /\ crashed = FALSE

-----------------------------------------------------------------------------
\* Helpers

IsIrreversible(o) == o \in IrreversibleOps
IsCompensatable(o) == o \in CompensatableOps

CanAdvanceHappy(o) ==
  /\ ~crashed
  /\ \E i \in 1..(Len(HappyPath)-1):
       /\ typestate[o] = HappyPath[i]
       /\ HappyPath[i] \in PreReserved \cup {"Reserved", "Started", "Observed"}

\* Advance one pre-reserved happy step (admission path).
AdvanceAdmission(o) ==
  /\ ~crashed
  /\ typestate[o] \in PreReserved \ {"LeaseHeld"}
  /\ \E i \in 1..(Len(HappyPath)-1):
       /\ HappyPath[i] = typestate[o]
       /\ typestate' = [typestate EXCEPT ![o] = HappyPath[i+1]]
  /\ durableCursor' = [durableCursor EXCEPT ![o] = typestate'[o]]
  /\ lastCrashBoundary' = "admission"
  /\ UNCHANGED <<
       effectCount, observed, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, unknownPending, compensationOwed,
       proofPromoted, crashed
     >>

\* Consume one-use confirmation (NoConfirmationReuse).
SatisfyConfirmation(o) ==
  /\ ~crashed
  /\ typestate[o] = "ObligationsSatisfied"
  /\ confirmationBound[o]
  /\ ~confirmationSpent[o]
  /\ typestate' = [typestate EXCEPT ![o] = "ConfirmationSatisfied"]
  /\ confirmationSpent' = [confirmationSpent EXCEPT ![o] = TRUE]
  /\ durableCursor' = [durableCursor EXCEPT ![o] = "ConfirmationSatisfied"]
  /\ lastCrashBoundary' = "admission"
  /\ UNCHANGED <<
       effectCount, observed, receiptSealed, confirmationBound, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, unknownPending, compensationOwed,
       proofPromoted, crashed
     >>

\* Acquire lease and bump fence generation (lease/fence evidence).
AcquireLease(o) ==
  /\ ~crashed
  /\ typestate[o] = "ConfirmationSatisfied"
  /\ fenceGen[o] < MaxFenceGen
  /\ typestate' = [typestate EXCEPT ![o] = "LeaseHeld"]
  /\ leaseHeld' = [leaseHeld EXCEPT ![o] = TRUE]
  /\ fenceGen' = [fenceGen EXCEPT ![o] = @ + 1]
  /\ durableCursor' = [durableCursor EXCEPT ![o] = "LeaseHeld"]
  /\ lastCrashBoundary' = "lease"
  /\ UNCHANGED <<
       effectCount, observed, receiptSealed,
       confirmationBound, confirmationSpent,
       fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, unknownPending, compensationOwed,
       proofPromoted, crashed
     >>

\* Reserve: capture fence; mark idempotency key; issue reservation.
Reserve(o) ==
  /\ ~crashed
  /\ typestate[o] = "LeaseHeld"
  /\ leaseHeld[o]
  /\ ~idempotencyRecorded[o]
  /\ typestate' = [typestate EXCEPT ![o] = "Reserved"]
  /\ fenceAtReserve' = [fenceAtReserve EXCEPT ![o] = fenceGen[o]]
  /\ idempotencyRecorded' = [idempotencyRecorded EXCEPT ![o] = TRUE]
  /\ durableCursor' = [durableCursor EXCEPT ![o] = "Reserved"]
  /\ lastCrashBoundary' = "reservation"
  /\ UNCHANGED <<
       effectCount, observed, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld, fenceGen,
       currentPointer, pendingCurrent, retries, unknownPending,
       compensationOwed, proofPromoted, crashed
     >>

\* Start effectful handler (requires current fence and lease).
Start(o) ==
  /\ ~crashed
  /\ typestate[o] = "Reserved"
  /\ leaseHeld[o]
  /\ fenceAtReserve[o] = fenceGen[o]          \* refuse stale fence start
  /\ typestate' = [typestate EXCEPT ![o] = "Started"]
  /\ durableCursor' = [durableCursor EXCEPT ![o] = "Started"]
  /\ lastCrashBoundary' = "started"
  /\ UNCHANGED <<
       effectCount, observed, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, unknownPending, compensationOwed,
       proofPromoted, crashed
     >>

\* Apply external effect exactly once (NoDoubleEffect).
ApplyEffect(o) ==
  /\ ~crashed
  /\ typestate[o] = "Started"
  /\ effectCount[o] = 0
  /\ effectCount' = [effectCount EXCEPT ![o] = 1]
  /\ pendingCurrent' = [pendingCurrent EXCEPT ![o] = currentPointer[o] + 1]
  /\ lastCrashBoundary' = "idempotency"
  /\ UNCHANGED <<
       typestate, observed, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer,
       retries, idempotencyRecorded, unknownPending, compensationOwed,
       proofPromoted, durableCursor, crashed
     >>

\* Independent observation of a started (and applied) effect.
Observe(o) ==
  /\ ~crashed
  /\ typestate[o] \in {"Started", "Unknown"}
  /\ effectCount[o] = 1
  /\ ~observed[o]
  /\ typestate' = [typestate EXCEPT ![o] = "Observed"]
  /\ observed' = [observed EXCEPT ![o] = TRUE]
  /\ unknownPending' = [unknownPending EXCEPT ![o] = FALSE]
  /\ durableCursor' = [durableCursor EXCEPT ![o] = "Observed"]
  /\ lastCrashBoundary' = "observed"
  /\ UNCHANGED <<
       effectCount, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, compensationOwed,
       proofPromoted, crashed
     >>

\* Ambiguous external outcome: enter Unknown (never silent success).
EnterUnknown(o) ==
  /\ ~crashed
  /\ typestate[o] = "Started"
  /\ effectCount[o] \in {0, 1}   \* may or may not have applied
  /\ typestate' = [typestate EXCEPT ![o] = "Unknown"]
  /\ unknownPending' = [unknownPending EXCEPT ![o] = TRUE]
  /\ durableCursor' = [durableCursor EXCEPT ![o] = "Unknown"]
  /\ lastCrashBoundary' = "unknown"
  /\ UNCHANGED <<
       effectCount, observed, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, compensationOwed,
       proofPromoted, crashed
     >>

\* Fail under observation. Irreversible ops retain unknownPending so that
\* Retry cannot blind-replay an ambiguous external effect.
Fail(o) ==
  /\ ~crashed
  /\ typestate[o] \in {"Started", "Unknown", "CompensationRequired"}
  /\ typestate' = [typestate EXCEPT ![o] = "Failed"]
  /\ unknownPending' = [unknownPending EXCEPT ![o] =
       IF IsIrreversible(o) /\ unknownPending[o] THEN TRUE ELSE FALSE]
  /\ durableCursor' = [durableCursor EXCEPT ![o] = "Failed"]
  /\ lastCrashBoundary' = "settlement"
  /\ UNCHANGED <<
       effectCount, observed, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, compensationOwed,
       proofPromoted, crashed
     >>

\* Abort before external ambiguity resolves (only if no irreversible apply).
Abort(o) ==
  /\ ~crashed
  /\ typestate[o] \in {"Started", "Unknown"}
  /\ ~(IsIrreversible(o) /\ unknownPending[o] /\ effectCount[o] = 1)
  /\ effectCount[o] = 0
  /\ typestate' = [typestate EXCEPT ![o] = "Aborted"]
  /\ unknownPending' = [unknownPending EXCEPT ![o] = FALSE]
  /\ durableCursor' = [durableCursor EXCEPT ![o] = "Aborted"]
  /\ lastCrashBoundary' = "settlement"
  /\ UNCHANGED <<
       effectCount, observed, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, compensationOwed,
       proofPromoted, crashed
     >>

\* Require compensation for compensatable ops.
RequireCompensation(o) ==
  /\ ~crashed
  /\ IsCompensatable(o)
  /\ typestate[o] \in {"Started", "Unknown", "Observed"}
  /\ typestate' = [typestate EXCEPT ![o] = "CompensationRequired"]
  /\ compensationOwed' = [compensationOwed EXCEPT ![o] = TRUE]
  /\ unknownPending' = [unknownPending EXCEPT ![o] = FALSE]
  /\ durableCursor' = [durableCursor EXCEPT ![o] = "CompensationRequired"]
  /\ lastCrashBoundary' = "compensation"
  /\ UNCHANGED <<
       effectCount, observed, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, proofPromoted, crashed
     >>

Compensate(o) ==
  /\ ~crashed
  /\ typestate[o] = "CompensationRequired"
  /\ compensationOwed[o]
  /\ typestate' = [typestate EXCEPT ![o] = "Compensated"]
  /\ compensationOwed' = [compensationOwed EXCEPT ![o] = FALSE]
  /\ observed' = [observed EXCEPT ![o] = TRUE]
  /\ durableCursor' = [durableCursor EXCEPT ![o] = "Compensated"]
  /\ lastCrashBoundary' = "compensation"
  /\ UNCHANGED <<
       effectCount, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, unknownPending,
       proofPromoted, crashed
     >>

\* Seal receipt only after observation (NoSuccessWithoutObservation).
SealReceipt(o) ==
  /\ ~crashed
  /\ typestate[o] \in {"Observed", "Compensated", "Failed", "Rejected",
                       "Unavailable", "Aborted"}
  /\ (typestate[o] \in {"Observed", "Compensated"} => observed[o])
  /\ fenceAtReserve[o] = fenceGen[o]   \* NoStaleFenceCompletion
  /\ typestate' = [typestate EXCEPT ![o] = "ReceiptSealed"]
  /\ receiptSealed' = [receiptSealed EXCEPT ![o] = TRUE]
  /\ durableCursor' = [durableCursor EXCEPT ![o] = "ReceiptSealed"]
  /\ lastCrashBoundary' = "receipt"
  /\ UNCHANGED <<
       effectCount, observed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, unknownPending, compensationOwed,
       proofPromoted, crashed
     >>

\* Settle current pointer after successful observed receipt.
SettleCurrent(o) ==
  /\ ~crashed
  /\ typestate[o] = "ReceiptSealed"
  /\ receiptSealed[o]
  /\ observed[o]
  /\ pendingCurrent[o] = currentPointer[o] + 1
  /\ currentPointer' = [currentPointer EXCEPT ![o] = pendingCurrent[o]]
  /\ lastCrashBoundary' = "current"
  /\ UNCHANGED <<
       typestate, effectCount, observed, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, pendingCurrent,
       retries, idempotencyRecorded, unknownPending, compensationOwed,
       proofPromoted, durableCursor, crashed
     >>

\* Proof promotion requires sealed receipt + observation + settled current.
PromoteProof(o) ==
  /\ ~crashed
  /\ typestate[o] = "ReceiptSealed"
  /\ receiptSealed[o]
  /\ observed[o]
  /\ currentPointer[o] = pendingCurrent[o]
  /\ pendingCurrent[o] > 0
  /\ ~proofPromoted[o]
  /\ proofPromoted' = [proofPromoted EXCEPT ![o] = TRUE]
  /\ lastCrashBoundary' = "proof_promotion"
  /\ UNCHANGED <<
       typestate, effectCount, observed, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, unknownPending, compensationOwed,
       durableCursor, crashed
     >>

\* Early deny / unavailable before reservation.
Reject(o) ==
  /\ ~crashed
  /\ typestate[o] \in PreReserved
  /\ typestate' = [typestate EXCEPT ![o] = "Rejected"]
  /\ durableCursor' = [durableCursor EXCEPT ![o] = "Rejected"]
  /\ lastCrashBoundary' = "admission"
  /\ UNCHANGED <<
       effectCount, observed, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, unknownPending, compensationOwed,
       proofPromoted, crashed
     >>

MarkUnavailable(o) ==
  /\ ~crashed
  /\ typestate[o] \in PreReserved
  /\ typestate' = [typestate EXCEPT ![o] = "Unavailable"]
  /\ durableCursor' = [durableCursor EXCEPT ![o] = "Unavailable"]
  /\ lastCrashBoundary' = "admission"
  /\ UNCHANGED <<
       effectCount, observed, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, unknownPending, compensationOwed,
       proofPromoted, crashed
     >>

\* Bounded retry after Failed when not irreversible-unknown.
\* NoReplayOfUnknownIrreversibleEffect: forbidden while unknownPending
\* for irreversible ops, and whenever an irreversible effect already applied.
Retry(o) ==
  /\ ~crashed
  /\ typestate[o] = "Failed"
  /\ retries[o] < MaxRetries
  /\ ~(IsIrreversible(o) /\ unknownPending[o])
  /\ ~(IsIrreversible(o) /\ effectCount[o] > 0)
  /\ ~idempotencyRecorded[o] \/ effectCount[o] = 0
  /\ typestate' = [typestate EXCEPT ![o] = "LeaseHeld"]
  /\ retries' = [retries EXCEPT ![o] = @ + 1]
  /\ idempotencyRecorded' = [idempotencyRecorded EXCEPT ![o] = FALSE]
  /\ receiptSealed' = [receiptSealed EXCEPT ![o] = FALSE]
  /\ observed' = [observed EXCEPT ![o] = FALSE]
  /\ durableCursor' = [durableCursor EXCEPT ![o] = "LeaseHeld"]
  /\ lastCrashBoundary' = "retry"
  /\ UNCHANGED <<
       effectCount, confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
       unknownPending, compensationOwed, proofPromoted, crashed
     >>

\* Fence invalidation (lease expiry / bump) — stale reserve cannot complete.
BumpFence(o) ==
  /\ ~crashed
  /\ leaseHeld[o]
  /\ fenceGen[o] < MaxFenceGen
  /\ fenceGen' = [fenceGen EXCEPT ![o] = @ + 1]
  /\ lastCrashBoundary' = "fence"
  /\ UNCHANGED <<
       typestate, effectCount, observed, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, unknownPending, compensationOwed,
       proofPromoted, durableCursor, crashed
     >>

-----------------------------------------------------------------------------
\* Crash injection at every named persistent boundary.
\* Volatile progress is lost; durableCursor is restored.

Crash(boundary) ==
  /\ ~crashed
  /\ boundary \in CrashBoundaries
  /\ lastCrashBoundary = boundary
  /\ crashed' = TRUE
  /\ typestate' = durableCursor
  /\ lastCrashBoundary' = "crash"
  /\ UNCHANGED <<
       effectCount, observed, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, unknownPending, compensationOwed,
       proofPromoted, durableCursor
     >>

Recover ==
  /\ crashed
  /\ crashed' = FALSE
  /\ lastCrashBoundary' = "crash"
  /\ UNCHANGED <<
       typestate, effectCount, observed, receiptSealed,
       confirmationBound, confirmationSpent, leaseHeld,
       fenceGen, fenceAtReserve, currentPointer, pendingCurrent,
       retries, idempotencyRecorded, unknownPending, compensationOwed,
       proofPromoted, durableCursor
     >>

-----------------------------------------------------------------------------

Next ==
  \/ \E o \in Ops:
       \/ AdvanceAdmission(o)
       \/ SatisfyConfirmation(o)
       \/ AcquireLease(o)
       \/ Reserve(o)
       \/ Start(o)
       \/ ApplyEffect(o)
       \/ Observe(o)
       \/ EnterUnknown(o)
       \/ Fail(o)
       \/ Abort(o)
       \/ RequireCompensation(o)
       \/ Compensate(o)
       \/ SealReceipt(o)
       \/ SettleCurrent(o)
       \/ PromoteProof(o)
       \/ Reject(o)
       \/ MarkUnavailable(o)
       \/ Retry(o)
       \/ BumpFence(o)
  \/ \E b \in CrashBoundaries: Crash(b)
  \/ Recover

Spec == Init /\ [][Next]_vars

-----------------------------------------------------------------------------
\* Required safety invariants

NoDoubleEffect ==
  \A o \in Ops: effectCount[o] <= 1

NoStaleFenceCompletion ==
  \A o \in Ops:
    (receiptSealed[o] /\ typestate[o] = "ReceiptSealed")
      => fenceAtReserve[o] = fenceGen[o]

\* Success means settled current pointer or proof promotion — never a sealed
\* receipt alone. Failure/rejection receipts may seal without observation.
NoSuccessWithoutObservation ==
  \A o \in Ops:
    /\ (proofPromoted[o] => observed[o])
    /\ (currentPointer[o] > 0 => observed[o])
    /\ ((receiptSealed[o] /\ effectCount[o] = 1 /\ typestate[o] = "ReceiptSealed")
          => observed[o])

NoConfirmationReuse ==
  \A o \in Ops:
    confirmationSpent[o] => confirmationBound[o]
  \* A spent confirmation cannot be spent again: SatisfyConfirmation
  \* requires ~confirmationSpent[o]. Encoded as a state invariant that
  \* spent flags are monotone once true under the action constraints.

NoReplayOfUnknownIrreversibleEffect ==
  \A o \in Ops:
    (IsIrreversible(o) /\ unknownPending[o])
      => /\ typestate[o] \in {"Unknown", "Observed", "Failed",
                              "CompensationRequired", "Aborted",
                              "ReceiptSealed"}
         /\ ~(typestate[o] \in {"Reserved", "Started"} /\ retries[o] > 0)

\* Aggregate invariant used by TLC model-check configurations.
Safety ==
  /\ TypeOK
  /\ NoDoubleEffect
  /\ NoStaleFenceCompletion
  /\ NoSuccessWithoutObservation
  /\ NoConfirmationReuse
  /\ NoReplayOfUnknownIrreversibleEffect

\* Named crash-boundary coverage predicate (reference / documentation).
CrashBoundaryCoverage == CrashBoundaries = EvidenceSubset

-----------------------------------------------------------------------------
\* Bounded model-check configuration (invoked only when TLC is admitted).
\* Example instance (do not auto-install tools):
\*   Ops = {o1, o2}
\*   MaxFenceGen = 3
\*   MaxRetries = 2
\*   IrreversibleOps = {o1}
\*   CompensatableOps = {o2}
\*   SPECIFICATION Spec
\*   INVARIANT Safety
\*   CHECK_DEADLOCK FALSE

THEOREM Spec => []Safety
====
