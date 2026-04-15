# Automated Business Network

A planned network of **10 automated businesses** run by software with
a single human owner (the "Principal") as approver and signer.

Status: **Planning committee convened (2026-04-15).** Awaiting
Principal's answers to `committee/OPEN_QUESTIONS.md`.

## Layout

```
automated_business_network/
  README.md                 <- this file
  committee/
    CHARTER.md              <- mission, seats, decision rules
    OPEN_QUESTIONS.md       <- questions the Principal must answer
    CANDIDATE_VENTURES.md   <- long list of 20, will be cut to 10
    DECISIONS.md            <- (created once answers arrive)
  ventures/                 <- one folder per selected venture
```

## Principles

1. **Real money only.** No venture ships without a payment rail and
   a pricing page.
2. **Human at the top.** The Principal signs every contract, approves
   every outbound payment over a threshold, and holds the kill switch.
3. **One platform, ten P&Ls.** Shared auth, payments, queue,
   observability; each venture is a module.
4. **Kill criteria before launch.** If a venture misses its 90-day
   milestone it is paused automatically.
5. **No dark patterns, no spam, no regulatory grey zones** without
   written sign-off from General Counsel.
