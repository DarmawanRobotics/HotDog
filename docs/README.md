# Dharma documentation

Everything here renders on GitHub (also in a private repository): the guide is plain Markdown,
the manual and the paper are committed as PDFs.

| Read                                           |                                                                                                                                                                             |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [guide/](guide/README.md)                      | the guide: getting started, architecture, robot profile, topics, safety, localization, mapping, navigation, health, simulation, tuning, a new product, troubleshooting, FAQ |
| [pdf/dharma_manual.pdf](pdf/dharma_manual.pdf) | the technical manual: architecture, every subsystem with its models and parameters, safety case, interfaces, development, traceability of every fixed defect                |
| [pdf/dharma_paper.pdf](pdf/dharma_paper.pdf)   | the paper describing Dharma's methods and evaluation (IEEE conference format)                                                                                               |

| Sources                |                                                                                 |
| ---------------------- | ------------------------------------------------------------------------------- |
| [manual/](manual/)     | the technical manual (LaTeX)                                                    |
| [paper/](paper/)       | the paper (LaTeX, IEEEtran)                                                     |
| [diagrams/](diagrams/) | draw.io sources, exported to `pdf/` (manual, paper) and `svg/` (guide, READMEs) |

## Guide

Start at [guide/README.md](guide/README.md): [Getting Started](guide/Getting-Started.md) ·
[Architecture](guide/Architecture.md) · [Robot Profile](guide/Robot-Profile.md) ·
[Topics and Services](guide/Topics-and-Services.md) · [Safety](guide/Safety.md) ·
[Localization](guide/Localization.md) · [Mapping and Sites](guide/Mapping-and-Sites.md) ·
[Navigation](guide/Navigation.md) · [Health](guide/Health.md) ·
[Simulation](guide/Simulation.md) · [Tuning](guide/Tuning.md) ·
[New Product from Template](guide/New-Product-from-Template.md) ·
[Contributing](guide/Contributing.md) · [Troubleshooting](guide/Troubleshooting.md) ·
[FAQ](guide/FAQ.md).

## Manual

`manual/dharma_manual.tex` with one file per chapter in `manual/chapters/`. The parameter and
interface tables in `manual/generated/` come from the code: `make reference SRC=<dir with the
dharma_* checkouts>` regenerates them (`manual/tools/reference.py`). `manual/tools/brake_test.py`
measures a robot's braking limits (chapter 3).

## Diagrams

| Diagram            |                                                                          |
| ------------------ | ------------------------------------------------------------------------ |
| `layers`           | the layers with the safety column, on dharma_utils and interfaces        |
| `dataflow`         | the nodes and the main topics between them                               |
| `tf_tree`          | `map -> odom -> camera_init -> body -> base_link` and who publishes what |
| `repos`            | the repository dependency graph                                          |
| `safety_pipeline`  | sources, arbitration, envelope, protective field, e-stop and re-arm      |
| `follower_fsm`     | the path follower's states and transitions                               |
| `localization_ekf` | predict, gated updates and the `map -> odom` publication                 |
| `ci`               | lint and the Foxy / Humble / Jazzy build and test matrix                 |

## Build

```bash
make -C docs              # diagrams (when draw.io is installed), then the manual and the paper
make -C docs diagrams     # diagrams/*.drawio -> diagrams/pdf (cropped) and diagrams/svg
make -C docs manual       # build/manual/dharma_manual.pdf
make -C docs paper        # build/paper/dharma.pdf
make -C docs pdf          # manual + paper, copied to pdf/ (commit them after a change)
make -C docs clean        # remove build/ (the exported diagrams are committed and kept)
```

Needs a LaTeX installation with latexmk and IEEEtran; draw.io (`drawio`, headless through
`xvfb-run`) only to re-export the diagrams. Each package documents its own nodes, topics and
parameters in its README. `scripts/init_project.py` removes the manual, the paper, the diagram
sources, the PDFs and the guide from a product made from the template and replaces this index
(`--keep-docs` keeps them).
