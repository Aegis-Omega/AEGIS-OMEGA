# OpenAI Researcher Access Program — AEGIS Ω Draft

Status: READY FOR OPERATOR REVIEW — NOT SUBMITTED
Current program support: up to USD 1,000 in OpenAI API credits, valid 12 months; applications reviewed quarterly.
Primary source: https://grants.openai.com/prog/openai_researcher_access_program/

## Project title

**Operator-Model Hallucination: Measuring Latent-State Errors That Change Agent Routing and Authority**

## Research summary

Large language model failures are commonly evaluated at the output level: factual hallucination, incorrect reasoning, unsafe content, or task failure. Agentic systems introduce an earlier failure surface. Before generating an answer or invoking a tool, a system may infer a latent state such as user intent, user state, task risk, or environmental context. If that inference is wrong, the downstream response can be internally coherent while the routing, safety posture, or authority decision is inappropriate.

This project will evaluate these upstream latent-state errors using controlled framing perturbations, explicit corrections, and evidence-bound calibration. The goal is to measure when semantically equivalent inputs cause unjustified changes in inferred operator state or policy routing, and whether an evidence threshold can reduce those errors without preventing legitimate safety responses.

## Core distinction

```text
CONTENT_RISK != USER_STATE
MODEL_CONFIDENCE != EVIDENCE
INFERENCE(USER_STATE) != ESTABLISHED(USER_STATE)
ESTABLISHED(USER_STATE) != AUTHORITY_TO_CHANGE_POLICY
```

## Research questions

1. How sensitive are model/user-state inferences to framing changes that preserve task meaning?
2. When a user explicitly corrects a model's interpretation, how quickly does the inferred state update?
3. Does an initial safety or intent hypothesis persist after contradicting evidence?
4. Can model confidence predict whether a latent-state inference is correct?
5. Can evidence-bound routing reduce unsupported user-state assertions while preserving appropriate conservative behavior for genuine content risk?
6. Are these errors stable across models, contexts, and repeated sessions?

## Experimental design

### Controlled minimal-pair probes

Create semantically matched prompts that vary:
- tone;
- ambiguity;
- adversarial framing;
- explicit uncertainty;
- technical versus colloquial vocabulary;
- order of contextual information.

Measure changes in:
- inferred intent/state labels where observable;
- clarification behavior;
- safety routing;
- unsupported psychological/user-state claims;
- tool selection;
- refusal/deference behavior.

### Explicit-correction probes

After a model forms an interpretation, provide a clear correction and measure:
- posterior stickiness;
- revision latency;
- route hysteresis;
- contradiction responsiveness.

### Evidence-bound intervention

Compare baseline behavior to a constrained routing policy where latent operator hypotheses remain advisory unless supported by specified evidence classes.

## Metrics

- Framing Sensitivity;
- Posterior Stickiness;
- Revision Latency;
- Contradiction Responsiveness;
- Route Hysteresis;
- User-State Overreach Rate;
- Policy Elevation Error;
- Meta-model calibration error.

One candidate calibration metric is:

`MetaHD = mean(|predicted_correctness - subsequently_supported_correctness|)`

The project will test whether this scalar is useful; it will not assume it is sufficient.

## Existing implementation base

AEGIS Ω contains a draft evidence-bounded operator meta-model implementation that explicitly separates:

- latent `USER_STATE`, `USER_INTENT`, and `USER_PREFERENCE` hypotheses;
- `CONTENT_RISK` and `TASK_CONTEXT`;
- advisory, routing-only, and assertable authority;
- one-turn routing from persistent policy changes.

The research will evaluate the idea empirically rather than treating the implementation as evidence that it works.

## Requested API use

Credits would be used to run controlled repeated experiments across available OpenAI models and experimental conditions, including adversarial and natural framing variations.

Planned use:
- baseline and intervention conditions;
- repeated trials for variance estimates;
- evaluation/judging where methodologically appropriate;
- systematic correction and contradiction probes.

No project objective requires harmful or unauthorized activity.

## Expected outputs

1. open benchmark dataset of controlled framing/correction probes;
2. reproducible evaluation harness;
3. empirical results across model/configuration conditions;
4. analysis of false-positive safety/user-state inference;
5. evidence-bound routing intervention results;
6. research paper/preprint with limitations and negative results.

## Relevance to OpenAI program themes

The project directly addresses:

- robustness to natural prompt perturbations;
- adversarial reliability;
- responsible deployment;
- transparency of surprising model behavior;
- red-teaming methods for deployment decisions.

## Research integrity

The study will not claim access to proprietary hidden chain-of-thought or undocumented internal classifiers. It will measure observable system behavior and infer hidden-state hypotheses only where experimental controls justify them.

Correlation between an observable response difference and a specific internal mechanism will not be treated as direct proof of that mechanism.

## Operator

Tarik Skalić
Bihać, Bosnia and Herzegovina
AEGIS Ω / Aegis-Omega

## Before submission

- [ ] map draft to exact application form fields;
- [ ] choose experiment size within USD 1,000 credit budget;
- [ ] add public repository/project link;
- [ ] specify data-sharing/publication plan;
- [ ] operator review;
- [ ] submit before the next quarterly review window.
