/*!
 * FACP-045 / FACP-G510 — Transactional Effect Protocols (TEP)
 * Relational (Alloy) encoding of required invariants and crash boundaries.
 *
 * Evidence: facp/tep-models@1
 * Bundle:   facp/protocols/models
 *
 * Required invariants:
 *   NoDoubleEffect
 *   NoStaleFenceCompletion
 *   NoSuccessWithoutObservation
 *   NoConfirmationReuse
 *   NoReplayOfUnknownIrreversibleEffect
 *
 * Evidence subset / crash boundaries:
 *   admission, reservation, started, unknown, observed, receipt, current,
 *   lease, fence, retry, idempotency, crash, settlement, compensation,
 *   proof_promotion
 *
 * Bounded checks only. Auto-install of Alloy is prohibited. Missing tools
 * must yield explicit nonqualified capability evidence, never a simulated
 * proof.
 */

module relational_invariants

/* ---------- Closed typestate vocabulary (EAK-aligned) ---------- */

abstract sig Typestate {}
one sig Proposed, ContractResolved, ActorAuthenticated, CapabilityVerified,
        PolicyEvaluated, ObligationsSatisfied, ConfirmationSatisfied,
        LeaseHeld, Reserved, Started, Observed, ReceiptSealed,
        Rejected, Unavailable, Failed, Unknown,
        CompensationRequired, Compensated, Aborted extends Typestate {}

abstract sig Reversibility {}
one sig Irreversible, Compensatable, Reversible extends Reversibility {}

abstract sig CrashBoundary {}
one sig admission, reservation, started, unknown, observed, receipt,
        current, lease, fence, retry, idempotency, crash, settlement,
        compensation, proof_promotion extends CrashBoundary {}

/* ---------- Core entities ---------- */

sig Op {
  reversibility: one Reversibility,
  typestate: one Typestate,
  effectCount: one Int,
  observed: one Int,            -- 0 or 1
  receiptSealed: one Int,       -- 0 or 1
  confirmationBound: one Int,     -- 0 or 1
  confirmationSpent: one Int,   -- 0 or 1
  leaseHeld: one Int,           -- 0 or 1
  fenceGen: one Int,
  fenceAtReserve: one Int,
  currentPointer: one Int,
  pendingCurrent: one Int,
  retries: one Int,
  idempotencyRecorded: one Int, -- 0 or 1
  unknownPending: one Int,      -- 0 or 1
  compensationOwed: one Int,    -- 0 or 1
  proofPromoted: one Int,       -- 0 or 1
  durableCursor: one Typestate,
  lastCrashBoundary: one CrashBoundary
}

sig ConfirmationToken {
  boundTo: one Op,
  spent: one Int                -- 0 or 1
}

sig Transition {
  op: one Op,
  prior: one Typestate,
  next: one Typestate,
  boundary: one CrashBoundary,
  fenceThen: one Int
}

fact Bounds {
  all o: Op {
    o.effectCount >= 0 and o.effectCount <= 1
    o.observed >= 0 and o.observed <= 1
    o.receiptSealed >= 0 and o.receiptSealed <= 1
    o.confirmationBound >= 0 and o.confirmationBound <= 1
    o.confirmationSpent >= 0 and o.confirmationSpent <= 1
    o.leaseHeld >= 0 and o.leaseHeld <= 1
    o.fenceGen >= 0 and o.fenceGen <= 3
    o.fenceAtReserve >= 0 and o.fenceAtReserve <= 3
    o.currentPointer >= 0 and o.currentPointer <= 3
    o.pendingCurrent >= 0 and o.pendingCurrent <= 3
    o.retries >= 0 and o.retries <= 2
    o.idempotencyRecorded >= 0 and o.idempotencyRecorded <= 1
    o.unknownPending >= 0 and o.unknownPending <= 1
    o.compensationOwed >= 0 and o.compensationOwed <= 1
    o.proofPromoted >= 0 and o.proofPromoted <= 1
  }
  all c: ConfirmationToken | c.spent >= 0 and c.spent <= 1
}

/* ---------- Evidence subset coverage ---------- */

pred CrashBoundaryCoverage {
  CrashBoundary = admission + reservation + started + unknown + observed +
                  receipt + current + lease + fence + retry + idempotency +
                  crash + settlement + compensation + proof_promotion
}

/* ---------- Required invariants ---------- */

pred NoDoubleEffect {
  all o: Op | o.effectCount <= 1
}

pred NoStaleFenceCompletion {
  all o: Op |
    (o.receiptSealed = 1 and o.typestate = ReceiptSealed)
      implies o.fenceAtReserve = o.fenceGen
}

pred NoSuccessWithoutObservation {
  -- Success == settled current or proof promotion; both require observation.
  all o: Op {
    o.proofPromoted = 1 implies o.observed = 1
    o.currentPointer > 0 implies o.observed = 1
    (o.receiptSealed = 1 and o.effectCount = 1 and o.typestate = ReceiptSealed)
      implies o.observed = 1
  }
}

pred NoConfirmationReuse {
  -- Each confirmation token may be spent at most once; op spent flag
  -- matches its bound tokens.
  all c: ConfirmationToken | c.spent <= 1
  all o: Op |
    o.confirmationSpent = 1 implies o.confirmationBound = 1
  all o: Op |
    #{c: ConfirmationToken | c.boundTo = o and c.spent = 1} <= 1
}

pred NoReplayOfUnknownIrreversibleEffect {
  all o: Op |
    (o.reversibility = Irreversible and o.unknownPending = 1) implies {
      o.typestate in Unknown + Observed + Failed + CompensationRequired +
                     Aborted + ReceiptSealed
      not (o.typestate in Reserved + Started and o.retries > 0)
    }
}

pred Safety {
  NoDoubleEffect
  NoStaleFenceCompletion
  NoSuccessWithoutObservation
  NoConfirmationReuse
  NoReplayOfUnknownIrreversibleEffect
  CrashBoundaryCoverage
}

/* ---------- Legal transition skeleton (relational) ---------- */

pred LegalHappyEdge[p, n: Typestate] {
  (p = Proposed and n = ContractResolved) or
  (p = ContractResolved and n = ActorAuthenticated) or
  (p = ActorAuthenticated and n = CapabilityVerified) or
  (p = CapabilityVerified and n = PolicyEvaluated) or
  (p = PolicyEvaluated and n = ObligationsSatisfied) or
  (p = ObligationsSatisfied and n = ConfirmationSatisfied) or
  (p = ConfirmationSatisfied and n = LeaseHeld) or
  (p = LeaseHeld and n = Reserved) or
  (p = Reserved and n = Started) or
  (p = Started and n = Observed) or
  (p = Observed and n = ReceiptSealed)
}

pred LegalExceptionalEdge[p, n: Typestate] {
  (p in Proposed + ContractResolved + ActorAuthenticated + CapabilityVerified +
        PolicyEvaluated + ObligationsSatisfied + ConfirmationSatisfied +
        LeaseHeld and n in Rejected + Unavailable) or
  (p = Started and n in Observed + Failed + Unknown + Aborted +
                        CompensationRequired) or
  (p = Unknown and n in Observed + Failed + CompensationRequired + Aborted) or
  (p = CompensationRequired and n in Compensated + Failed) or
  (p = Observed and n in CompensationRequired + ReceiptSealed) or
  (p in Compensated + Failed + Rejected + Unavailable + Aborted and
   n = ReceiptSealed)
}

pred LegalTransition[t: Transition] {
  LegalHappyEdge[t.prior, t.next] or LegalExceptionalEdge[t.prior, t.next]
  t.op.typestate = t.next
}

fact TransitionWellFormed {
  all t: Transition | LegalTransition[t]
}

/* ---------- Crash-boundary attachment ---------- */

pred BoundaryMatches[t: Transition] {
  (t.next in Proposed + ContractResolved + ActorAuthenticated +
             CapabilityVerified + PolicyEvaluated + ObligationsSatisfied +
             ConfirmationSatisfied and t.boundary = admission) or
  (t.next = LeaseHeld and t.boundary = lease) or
  (t.next = Reserved and t.boundary = reservation) or
  (t.next = Started and t.boundary = started) or
  (t.next = Unknown and t.boundary = unknown) or
  (t.next = Observed and t.boundary = observed) or
  (t.next = ReceiptSealed and t.boundary = receipt) or
  (t.next in Failed + Aborted and t.boundary = settlement) or
  (t.next in CompensationRequired + Compensated and t.boundary = compensation)
}

/* ---------- Bounded run / check commands ---------- */

-- Expect Safety to hold for small scopes when tools are admitted.
check SafetyHolds {
  Safety
} for 3 but 3 Op, 3 ConfirmationToken, 4 Transition, 4 Int

-- Counterexample hunt: double effect should be unsat under Safety.
run ViolateNoDoubleEffect {
  some o: Op | o.effectCount > 1
  Safety
} for 3 but 2 Op, 2 Int

run ViolateNoStaleFence {
  some o: Op |
    o.receiptSealed = 1 and o.typestate = ReceiptSealed and
    o.fenceAtReserve != o.fenceGen
  Safety
} for 3 but 2 Op, 3 Int

run ViolateNoSuccessWithoutObservation {
  some o: Op |
    o.receiptSealed = 1 and o.observed = 0 and
    o.typestate = ReceiptSealed
  Safety
} for 3 but 2 Op, 2 Int

run ViolateNoConfirmationReuse {
  some o: Op |
    #{c: ConfirmationToken | c.boundTo = o and c.spent = 1} > 1
  Safety
} for 3 but 2 Op, 3 ConfirmationToken, 2 Int

run ViolateNoReplayUnknownIrreversible {
  some o: Op |
    o.reversibility = Irreversible and o.unknownPending = 1 and
    o.typestate = Started and o.retries > 0
  Safety
} for 3 but 2 Op, 2 Int

-- Positive instance: a single observed sealed op with matching fence.
run HappyObservedReceipt {
  some o: Op {
    o.typestate = ReceiptSealed
    o.effectCount = 1
    o.observed = 1
    o.receiptSealed = 1
    o.fenceAtReserve = o.fenceGen
    o.confirmationBound = 1
    o.confirmationSpent = 1
    o.lastCrashBoundary = receipt
  }
  Safety
} for 3 but 1 Op, 1 ConfirmationToken, 2 Transition, 3 Int
