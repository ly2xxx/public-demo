# Talking points — final round (Riyaz)

Not for publishing. The post is the artefact; this is how to use it in the room.

## The 60-second frame

If asked how you think about agent platforms:

> "I treat an agent harness as ordinary software with one unusual component. The model is nondeterministic, so I can't test it the way I test a function — but everything around it is normal engineering, and that's the part I can make maintainable. So I apply the same rules I'd apply to any service: one reason to change per component, a uniform contract between nodes, extension points that don't require touching the core, and dependencies that point at interfaces rather than vendor SDKs. Then I add the two things classic design doesn't cover: an eval suite as the regression test, and hard budgets, because nondeterminism and cost are structural, not operational."

That paragraph does the work: it says backend discipline, it says you know where the discipline stops, and it doesn't oversell.

## Three lines that land with an engineering director

- **"The maker is never the judge."** Then the maker-checker parallel. It reframes an AI design choice as a control they already enforce in banking, which makes you legible to non-AI stakeholders.
- **"Model agnosticism is a behavioural claim, not an interface claim."** Most candidates will say "we're provider-agnostic". Saying why that's usually false — same signature, different contract, 99% vs 87% valid JSON — separates you immediately, and lands you on contract tests, which is twenty-year-old engineering.
- **"Context is the interface, and it has a meter running."** Interface Segregation is the only design principle where the engineering argument and the cost argument are identical. Directors carry budgets.

## Where to use your own repo

Have one concrete story ready — specifics beat frameworks:

- **The honest one:** your nodes reach the LLM boundary through a lazy import of the engine module, because that's where the tests monkeypatch. A dependency arrow bent by test convenience. You know it, you can name the fix (inject the boundary functions through run config), and you haven't done it yet. Volunteering a violation you understand reads as seniority; claiming a clean architecture reads as a demo.
- **The one that shows judgement:** every node receives all thirty state fields because that's LangGraph's model, not your choice. You didn't fight the framework; you know the mitigation is a typed slice per node. Knowing which battles aren't worth it is a lead-level signal.
- **The one that shows control thinking:** acceptance tests frozen before the work starts, so the thing writing the code cannot edit its own definition of done.

## Likely challenges, and answers

**"Isn't SOLID overkill for a prototype?"**
Yes, and most of it costs nothing if decided early — a uniform node signature is free on day one and expensive on day two hundred. The parts I'd defer are the platform pieces: gateway, registry policy, shared run store. Those earn their keep at the second team, not the first.

**"How do you know your harness still works after a model upgrade?"**
A frozen eval set of real tasks with known-good outcomes, run as a gate before the swap. Not a public benchmark — our tasks, our gates, pass/fail. That's the contract test for a component you can't unit test.

**"How would you roll this out across teams who already have their own agents?"**
I wouldn't consolidate the graphs; isolated harnesses are cheap. I'd standardise the four seams they'll inevitably share — model access, tool registration, run artefacts, eval gates — and leave everything above those seams to the teams. Standardise the interfaces, not the implementations.

**"What's the failure mode you worry about most?"**
Not hallucination. Silent capability drift after a model or prompt change, in a system with no eval gate to catch it — because nobody sees it until the output is already downstream.

## One thing to avoid

Don't present the five-row table as the answer. Present it as the map, then go straight to the two rows that are hard (Liskov, Interface Segregation) and the four things SOLID doesn't cover. Anyone can recite the mapping; the value you're demonstrating is knowing where it breaks down.
