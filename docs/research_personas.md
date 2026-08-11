# Research Personas

Anakrisis permits non-attributable research personas — "sock puppets" — and treats
them as good operational security rather than as a violation. Viewing a target from
your own account leaks your identity to them and, on several platforms, actively
notifies them. A persona is how you avoid that.

This page covers the reasoning and the edge cases. For the short version, see the
persona table in the [README](../README.md). For how the rules are evaluated, see
[doctrine.md](doctrine.md).

---

## The line is interaction, not the account

A persona **invents** an identity. Impersonation **borrows** a real person's. Only the
second is prohibited, and it is prohibited because it carries identity-theft,
fraud, and defamation exposure that has nothing to do with operational security.

| Permitted, and encouraged | Hard stop |
|---|---|
| Creating a non-attributable persona to view public content | Posing as a real, identifiable person |
| Viewing public profiles, posts, and pages while logged in as that persona | Any follow, request, message, comment, reaction, or story view directed at the target |

The rules implementing this live in `doctrine/disallowed_actions.yaml`:

| Rule | Severity | Fires on |
|---|---|---|
| `AR_RESEARCH_PERSONA` | `elevated` | Persona use — a heads-up, not a block |
| `AR_IMPERSONATE_REAL_PERSON` | `hard_stop` | Posing as a real, identifiable person |
| `AR_TARGET_CONTACT` | `hard_stop` | Any interaction with the target, from any account |
| `AR_RESTRICTED_CONTENT_ACCESS` | `hard_stop` | Reaching content the target has restricted |

`AR_TARGET_CONTACT` is the load-bearing one. Because persona use is permitted, the
boundary that matters is interaction — so that rule catches engagement verbs
(comment, reply, react, like, share, tag, mention, subscribe, add) and not just
direct messaging. It fires on the action regardless of which account performs it.

---

## Three things that catch people out

### A persona does not unlock private content

This is the most common misreading. A persona buys you **unattributed viewing of
public material**. It does not get you into a private account, because reaching that
requires a follow request — which is interaction, and a hard stop.
`AR_RESTRICTED_CONTENT_ACCESS` still fires on "use a burner account to view their
private profile", and that is intended behaviour, not a gap.

### A logged-in view is not always silent

"Passive" from your side is not always passive from the target's:

- **LinkedIn** shows the account holder who viewed their profile
- **Instagram** and **Snapchat** show who viewed a story
- Various platforms expose read receipts or "seen" state

This is why story and profile views are in the `AR_TARGET_CONTACT` trigger list
rather than being treated as viewing. A view that notifies is an interaction.

It is also why authenticated persona viewing is classified **`passive_plus`**, not
`passive_only`. Logging in creates an account footprint, so calling it `passive_only`
would misrepresent the trace it leaves. See `doctrine/method_classes.yaml`.

### Platform terms

Some platforms' terms don't allow secondary accounts, so a persona can be suspended.
Anakrisis surfaces this once as an `elevated` note and moves on — it is a thing to
know, not a reason to stop.

---

## Operating a persona

Requirements carried in `passive_plus`:

- **Non-attributable.** Never a real person's name, photo, or biography, and nothing
  traceable back to you.
- **View-only.** No follows, requests, messages, comments, reactions, or story views.
- **Recorded.** Note persona use in the case file, including which platforms were
  accessed and what was visible at the time.

Anakrisis is advisory throughout. It flags, explains, and offers a re-scoped
alternative; it does not halt execution. The decision, and responsibility for it,
stays with the investigator.
