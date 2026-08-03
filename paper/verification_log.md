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
| Dragan and Srinivasa, Generating Legible Motion, RSS 2013 | pending | Section headings confirmed from the PDF, including "The Unpredictability of Legibility" and "Constrained Legibility Optimization". Secondary sources state that the paper observes legibility pushing a trajectory closer to an obstacle than expected, and that a trust region of predictability bounds this. Those sentences have not been read in the body. This is the highest priority check in the log: if the paper already treats the obstacle interaction quantitatively, the safety-constrained framing is a narrowing of existing work rather than a gap, and it has to be described that way. Due before the scenario suite is designed, because the scenarios encode the claim. |
| Amirian, Abrini and Chetouani, Legibot, 2024 | body checked | Legibility in a cost-based local planner. Obstacle distance and rate of approach appear as terms in the task cost. Reports legibility scores from a user study and no quantitative path cost comparison against the baseline. Names the balance between task efficiency and legibility as an open question. No benchmark or code release stated. |
| Bastarache, Nielsen and Smith, legible and predictable navigation among multiple agents, ICRA 2023 | pending | Fetch returned a PDF structure dump rather than text. Existence and reliance on Dragan's formulation confirmed; nothing else. Needs a proper read before it is cited for anything. |
| Wallkotter, Chetouani and Castellano, A new approach to evaluating legibility, arXiv 2022 | body checked | Compares ten legibility frameworks on framework-independent trajectories across two scenarios, evaluated by human observers. The honest contrast for the judge-free claim: they evaluate frameworks against people, this benchmark evaluates planners against an exactly computed observer. The difference has to be argued rather than assumed to be an improvement. |
| Francis et al., Principles and Guidelines for Evaluating Social Robot Navigation Algorithms, ACM Transactions on Human-Robot Interaction | pending | Sets out eight principles that place safety and legibility side by side, which is close to this project's framing. Two things to check in the body: whether it calls for runnable instruments, in which case it is cited as motivation rather than positioned around, and whether it proposes computed legibility metrics or leaves them to human judgement. |
| Shi, Grislain, Sigaud and Chetouani, Controlling Intent Expressiveness in Robot Motion with Diffusion Models, 2025 | metadata only | Controllable legibility across a spectrum using an Information Potential Field. Abstract does not mention obstacles or constraint satisfaction; that absence is not yet confirmed from the body. |
| Mahadevan et al., Generative Expressive Robot Behaviors using Large Language Models, HRI 2024 | metadata only | Closest existing work on language models and expressive motion. Needs a read before the language model framing is written. |
| Sisbot and colleagues, Planning Safe and Legible Hand-over Motions for Human-Robot Interaction | pending | Safety and legibility posed together for manipulation handovers. Not read. Bibliographic details not yet confirmed. |

## Outstanding obligations

1. Read the body of Dragan and Srinivasa, RSS 2013, sections on the
   unpredictability of legibility and constrained legibility optimisation.
   Record whether obstacle interaction is quantified and whether
   constraint satisfaction is measured. Due before the scenario suite is
   designed.
2. Read Francis et al. for whether it calls for runnable instruments.
3. Read the two papers currently marked pending for lack of a usable text
   fetch, rather than citing them from search summaries.
4. A search for work newer than 4 August 2026 immediately before any
   submission.
