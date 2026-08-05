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
| Dragan, Lee and Srinivasa, Legibility and Predictability of Robot Motion, HRI 2013 | body checked 5 August 2026 | The formalism the observer model follows. Equations 8, 9 and 10 read in the body and compared line by line with the implementation; see below. |
| Dragan and Srinivasa, Generating Legible Motion, RSS 2013 | body checked 4 August 2026 | Read in full from the PDF. Four findings, each recorded in detail below. In short: the obstacle interaction is stated but not measured; the trust region is a bound on path cost and is our cost ceiling in different units; its purpose is the validity of the observer model rather than efficiency; and the paper reports the same multimodality we hit in the optimiser. |
| Amirian, Abrini and Chetouani, Legibot, 2024 | body checked | Legibility in a cost-based local planner. Obstacle distance and rate of approach appear as terms in the task cost. Reports legibility scores from a user study and no quantitative path cost comparison against the baseline. Names the balance between task efficiency and legibility as an open question. No benchmark or code release stated. |
| Bastarache, Nielsen and Smith, On Legible and Predictable Robot Navigation in Multi-Agent Environments, ICRA 2023 | body checked 5 August 2026 | Extends Dragan to dynamic goal regions for multi-agent passing. Reports minimum separation and minimum time-to-collision alongside legibility, which narrows our safety claim; see below. |
| Wallkotter, Chetouani and Castellano, A new approach to evaluating legibility, arXiv 2022 | body checked | Compares ten legibility frameworks on framework-independent trajectories across two scenarios, evaluated by human observers. The honest contrast for the judge-free claim: they evaluate frameworks against people, this benchmark evaluates planners against an exactly computed observer. The difference has to be argued rather than assumed to be an improvement. |
| Francis et al., Principles and Guidelines for Evaluating Social Robot Navigation Algorithms | body checked 4 August 2026 | Read from the arXiv version, 2306.16740v4. It calls for runnable instruments explicitly and endorses computed metrics for reproducibility, so it is cited as motivation and not positioned around. It names legibility as principle P3 and attributes it to Dragan rather than proposing a computed metric of its own. It also sets a condition this project has not met, recorded below. |
| Shi, Grislain, Sigaud and Chetouani, Controlling Intent Expressiveness in Robot Motion with Diffusion Models, 2025 | metadata only | Controllable legibility across a spectrum using an Information Potential Field. Abstract does not mention obstacles or constraint satisfaction; that absence is not yet confirmed from the body. |
| Mahadevan et al., Generative Expressive Robot Behaviors using Large Language Models, HRI 2024 | metadata only | Closest existing work on language models and expressive motion. Needs a read before the language model framing is written. |
| Mainprice, Sisbot, Simeon and Alami, Planning Safe and Legible Hand-over Motions for Human-Robot Interaction, 2010 | blocked | Cannot be read from here: HAL returns 403 behind anti-bot protection and Semantic Scholar returns nothing. Only a search summary is available, which is not a source. Recommendation is to drop it rather than cite it; see below. |

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

## Dragan, Lee and Srinivasa, HRI 2013, read in full 5 August 2026

The paper the observer model is taken from, and it had never been read
past its bibliographic details. Three findings.

**Our observer is their equation 8, exactly.** The paper derives
P(G | S to Q) proportional to exp(-C(S to Q) - C(optimal Q to G)) divided
by exp(-C(optimal S to G)), times the prior. Our exponent is
beta times (C*(S to G) - C(path so far) - C*(x to G)), normalised over the
goals with the prior. At beta = 1 these are the same expression. Beta is
our addition, an inverse temperature that the paper does not have, which
is why it travels in the observer's name.

**Our legibility metric is their equation 9, exactly**, including the
weighting: the integral of the belief in the true goal against f(t),
divided by the integral of f(t), with f(t) = T - t named in the text as
the example. Our implementation is the discrete form of that over the
sampled path.

**Both founding papers bound the cost, and they predicted what we
observed.** Equation 10 adds a regulariser, legibility minus lambda times
cost, and the reason given is that a robot can make a trajectory more and
more legible, never reaching a score of 1, while increasing cost more and
more. The RSS paper of the same year does it as a hard trust region
instead. So our cost ceiling is the hard variant of a bound both papers
apply, and the unbounded search we removed, which reached a cost ratio
near 3.6, is exactly the runaway equation 10 exists to prevent. That
strengthens the decision to drop the unbounded point and means the sweep
must cite this as prior art rather than presenting a ceiling as new.

Also worth carrying into the limitations: with multiple goals the score
cannot reach 1, so a legibility of 0.93 is not "93 per cent of the way to
perfect" and must never be described that way.

## Bastarache, Nielsen and Smith, ICRA 2023, read in full 5 August 2026

"On Legible and Predictable Robot Navigation in Multi-Agent Environments",
seven pages, code released. It extends Dragan's formalism to dynamic goal
regions so that the goal being inferred is which side the robot will pass
on, rather than which static target it is heading for.

This narrows contribution claim (a) further and the narrowing should be
stated rather than discovered by a reviewer. The paper reports minimum
distance to other agents and minimum time-to-collision, described in its
own words as a proxy for legibility and safety, alongside goal efficiency
and failure rate. So legibility and a safety quantity already appear in
one table in the legible-navigation literature.

What remains different here is narrower than "nobody reports safety with
legibility". It is: their safety quantity is proximity to moving agents
rather than satisfaction of a stated static constraint; they compare
policies rather than tracing a curve against a path cost budget; and they
present a navigation policy, not an instrument with proof-carrying
scenarios and released records.

## Mainprice, Sisbot, Simeon and Alami, 2010: not read, and blocked

The safe and legible hand-over paper cannot be read with the tools here.
The HAL record returns HTTP 403 behind anti-bot protection and the
Semantic Scholar page returns nothing. What is known comes from a search
summary: a workshop paper at IARP/IEEE-RAS/EURON 2010 in Toulouse,
handling three constraints named as safety, visibility and arm comfort.

That is not enough to cite under the rules this project works to, and the
summary suggests its "legible" is the human-aware costmap sense rather
than Dragan's goal-inference sense, which would make it a different
subject wearing the same word. The recommendation is to drop it rather
than cite it from a summary. If it is wanted, it needs fetching by hand
or through institutional access, and then reading.

## Outstanding obligations

1. Establish what, if anything, can be said about the validity of the
   legibility metric in this instrument, in the light of Francis
   guideline B6 and the bound Dragan places on their own user studies.
   This is a writing obligation rather than a reading one and it cannot
   be discharged by more citation. It is the largest open item.
2. Decide whether to cite the 2010 hand-over paper at all. It cannot be
   read from here and must not be cited from a summary.
3. Read Amirian, Abrini and Chetouani's Legibot and Shi et al.'s
   diffusion work in the body before either is cited for a finding.
   Both are currently at body checked and metadata only respectively,
   and neither is load bearing yet.
4. A search for work newer than 5 August 2026 immediately before
   submission.
