# Related work verification log

What has been read, what has been confirmed, and what has not. A claim is
only allowed into the draft once the row that supports it says the paper's
body was checked, not its abstract.

Status values: `body checked` means the relevant passage was read in the
paper itself; `metadata only` means the title, authors and venue were
confirmed but no finding has been attributed; `pending` means a claim is
being provisionally relied on and must be checked before it is written
down.

## First pass, 4 August 2026

| Work | Status | Note |
| --- | --- | --- |
| Dragan, Lee and Srinivasa, Legibility and Predictability of Robot Motion, HRI 2013 | metadata only | The formalism the observer model follows. Authors, venue and year confirmed against the CMU Robotics Institute record. |
| Dragan and Srinivasa, Generating Legible Motion, RSS 2013 | body checked 4 August 2026 | Read in full from the PDF. Four findings, each recorded in detail below. In short: the obstacle interaction is stated but not measured; the trust region is a bound on path cost and is our cost ceiling in different units; its purpose is the validity of the observer model rather than efficiency; and the paper reports the same multimodality we hit in the optimiser. |
| Amirian, Abrini and Chetouani, Legibot, 2024 | body checked | Legibility in a cost-based local planner. Obstacle distance and rate of approach appear as terms in the task cost. Reports legibility scores from a user study and no quantitative path cost comparison against the baseline. Names the balance between task efficiency and legibility as an open question. No benchmark or code release stated. |
| Bastarache, Nielsen and Smith, legible and predictable navigation among multiple agents, ICRA 2023 | pending | Fetch returned a PDF structure dump rather than text. Existence and reliance on Dragan's formulation confirmed; nothing else. Needs a proper read before it is cited for anything. |
| Wallkotter, Chetouani and Castellano, A new approach to evaluating legibility, arXiv 2022 | body checked | Compares ten legibility frameworks on framework-independent trajectories across two scenarios, evaluated by human observers. The honest contrast for the judge-free claim: they evaluate frameworks against people, this benchmark evaluates planners against an exactly computed observer. The difference has to be argued rather than assumed to be an improvement. |
| Francis et al., Principles and Guidelines for Evaluating Social Robot Navigation Algorithms | body checked 4 August 2026 | Read from the arXiv version, 2306.16740v4. It calls for runnable instruments explicitly and endorses computed metrics for reproducibility, so it is cited as motivation and not positioned around. It names legibility as principle P3 and attributes it to Dragan rather than proposing a computed metric of its own. It also sets a condition this project has not met, recorded below. |
| Shi, Grislain, Sigaud and Chetouani, Controlling Intent Expressiveness in Robot Motion with Diffusion Models, 2025 | metadata only | Controllable legibility across a spectrum using an Information Potential Field. Abstract does not mention obstacles or constraint satisfaction; that absence is not yet confirmed from the body. |
| Mahadevan et al., Generative Expressive Robot Behaviors using Large Language Models, HRI 2024 | metadata only | Closest existing work on language models and expressive motion. Needs a read before the language model framing is written. |
| Sisbot and colleagues, Planning Safe and Legible Hand-over Motions for Human-Robot Interaction | pending | Safety and legibility posed together for manipulation handovers. Not read. Bibliographic details not yet confirmed. |

## Dragan and Srinivasa, RSS 2013, read in full 4 August 2026

Four findings. The second and third change what this benchmark may
report, not merely how it is positioned.

**1. The obstacle interaction is stated, and not measured.** Section VIII
carries a paragraph headed "Obstacle Avoidance" which says that legibility
will move the trajectory, in their words, "much closer to the obstacle in
order to disambiguate between the two goals". So the phenomenon this
project was going to claim as its own observation is already in the
founding paper. What is not there is any measurement of it. Obstacles
enter through the cost functional as a CHOMP penalty for coming close,
which is a soft term inside the objective rather than a constraint;
clearance is never reported as a number; and constraint satisfaction is
not an axis of any result. The honest form of our contribution is
therefore not that anyone missed this. It is that it was noticed and left
qualitative, and this instrument makes it a measured, hard-constrained,
reported axis. That has to be written that way, with the paragraph cited.

**2. The trust region is a bound on path cost, and it is our cost
ceiling.** Section VI constrains the trajectory, in their words, "to stay
below a maximum cost in C during the optimization", giving the constraint
C on a trajectory at most beta. Our cost ceiling is the same constraint
expressed as a ratio against the optimal path rather than as an absolute
in their cost functional. The design we settled on independently is the
one the founding paper uses, which is reassuring for the design and means
the sweep must cite it rather than present the ceiling as a new idea. The
numerical value does not transfer: their beta is absolute and measured in
a sum-squared-velocity cost, ours is a ratio in path length.

**3. The purpose of that bound is the validity of the observer model, not
efficiency, and this disqualifies our unbounded sweep point.** The paper
is explicit that, in their words, "the legibility model can only be
trusted inside this trust region". The reason is that observers stop
reasoning the way the Boltzmann model assumes once motion becomes strange
enough: their follow-up study found users beginning to believe in a goal
that was not in the scene at all. Their main experiment found legibility
rising with the trust region up to a value they identify as beta star and
not improving beyond it.

This matters directly. Our sweep includes a point with no cost ceiling, at
which the optimiser reaches a cost ratio near 3.6. That is a legibility
number computed well outside the region in which anybody has shown the
formalism corresponds to what people perceive. It is not the far end of
the frontier; it is outside the domain of the model. Our observer also has
no "neither of these" option, so it cannot express the belief their
subjects actually formed, and its posterior will keep summing to one over
the declared goals however strange the motion becomes. That is a known
direction of error and it grows with the cost ratio.

**4. The multimodality we hit is reported there too.** Section VIII states
there is no guarantee the legibility objective is concave and that
different initialisations reach different local maxima. That is exactly
the defect that made our constrained planner return 0.5591 where 0.9264
was available, and it supports the structured multi-seeding rather than
making it look like an ad hoc patch.

## Francis et al., read 4 August 2026

**It calls for runnable instruments.** The abstract states the aim of
paving the road towards repeatable benchmarking criteria for social robot
navigation, and section VIII evaluates existing benchmarks against six
guidelines, B1 to B6. So it is cited as motivation. This project is an
instance of what it asks for, narrowed to one principle crossed with
another, and not something to be positioned against.

**It endorses computed metrics for exactly our reason.** Discussing the
expense and variance of human surveys, it says of algorithmic metrics that
they are, in their words, "cheap to compute and reproducible, properties
that are key for benchmarking", and guideline M2 is to validate first with
algorithmic metrics. Guideline B3 asks for baseline policies as a lower
bound and names a straight line planner as the example, which is the
shortest path baseline we already report against.

**It names legibility as principle P3 and does not give it a computed
metric.** The definition points at Dragan. So there is no competing
computed legibility metric in the guidelines to be measured against, which
leaves the gap this instrument fills, but also means we cannot claim to
implement their metric because they do not state one.

**It sets a condition this project has not met.** Guideline B6 says
objective metrics should be empirically validated to ensure they measure
what they purport to measure, and guideline B5 notes the field lacks a
good enough model of how humans react to robots. Our metric is exactly
specified and exactly reproducible, which is not the same as validated.
The only validity anchor available is Dragan's own user studies, and those
support the metric only inside the trust region. The paper must say this
plainly rather than let judge-free be read as judge-proof.

## Outstanding obligations

1. Read the two papers still marked pending, LPSNav and the safe and
   legible handover work, rather than citing them from search summaries.
   Neither is load bearing yet; both would be cited in related work.
2. Read Dragan, Lee and Srinivasa, HRI 2013, in the body. The observer
   model follows its formalism and only its bibliographic details have
   been confirmed. Lower priority than it looks, because the RSS paper
   restates the formalism and has now been read, but it should not stay
   at metadata only in a paper that leans on it.
3. Establish what, if anything, can be said about the validity of the
   legibility metric in this instrument, in the light of Francis
   guideline B6 and the bound Dragan places on their own user studies.
   This is a writing obligation rather than a reading one and it cannot
   be discharged by more citation.
4. A search for work newer than 4 August 2026 immediately before any
   submission.
