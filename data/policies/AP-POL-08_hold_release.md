# AP-POL-08 Hold release and segregation of duties

## §2.1 Multiple causes
When an invoice has several hold causes, they are resolved in priority order: fraud (bank change) first, then duplicates, vendor holds, e-invoice validation, currency/tax, missing receipt, quantity, price and finally approval. A lower-priority fix never overrides a higher-priority block.

## §3.1 Who may release a hold
Only users with the AP Manager role may release an invoice hold, and only after a second person approves the release. AP Clerks may investigate and recommend but never release.

## §3.2 Holds that may never be released by AP
AP may not release holds caused by an unverified bank-account change, a confirmed duplicate, a vendor-level hold or a failed e-invoice validation. These are resolved by the owning process (fraud review, rejection, vendor management, platform rejection).

## §3.3 Audit
Every release is recorded with the user, role, approver, justification and timestamp.
