# Documentation

| Guide                    | For                                                                                                                                  | Open                                                                             |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| **User Manual**          | operators: safety in the substation, teaching routes and targets, patrols, results, alerts. No robotics needed                       | [PDF](HotDog-User-Manual.pdf) · [source](manual/user-manual.md)                  |
| **Technician Guide**     | technicians: configuration layers, the M20, LiDARs and the protective field, inspection limits, maintenance, the parameter reference | [PDF](HotDog-Technician-Guide.pdf) · [source](technician/technician-guide.md)    |
| **Site Acceptance Test** | the handover at a substation: safety functions, navigation, inspection, reports and alerts, resilience, sign-off                     | [PDF](HotDog-Site-Acceptance-Test.pdf) · [source](acceptance/acceptance-test.md) |

The PDFs are A5, sized to read on a phone during a shift: open them here on GitHub or keep them
on the phone.

## Other documents

| Document                                  | Covers                                                            |
| ----------------------------------------- | ----------------------------------------------------------------- |
| [Commissioning](commissioning.md)         | a new M20 or a new substation, step by step with a check for each |
| [Operations](operations.md)               | the shift's tasks as `hotdog` commands, a quick reference         |
| [README](../README.md)                    | install, architecture, operate, develop                           |
| Package READMEs (`src/hotdog*/README.md`) | nodes, topics, services and parameters of each package            |
| [CONTRIBUTING](../CONTRIBUTING.md)        | branches, commits, code rules                                     |
| [CHANGELOG](../CHANGELOG.md)              | changes per version                                               |

## Rebuilding the PDFs

Rebuild after changing a guide, or any `src/*/config/*.yaml` (the Technician Guide reads its
parameter reference from them), and commit the PDFs with the change. CI builds them on every
push and warns when a committed PDF is older than its sources.

```bash
pip install weasyprint markdown pyyaml pillow   # macOS: brew install pango first
python3 docs/pdf/diagrams.py                     # the logo and the diagrams (after changing them)
python3 docs/pdf/build.py                        # every guide
python3 docs/pdf/build.py manual                 # one of: manual, technician, acceptance
```

| Path                                    | Holds                                                                                       |
| --------------------------------------- | ------------------------------------------------------------------------------------------- |
| `manual/`, `technician/`, `acceptance/` | the sources: Markdown with a YAML front matter (title, version, date, revisions)            |
| `manual/img/`                           | the diagrams (drawn by `pdf/diagrams.py`)                                                   |
| `pdf/build.py`                          | Markdown to A5 PDF with WeasyPrint: cover, contents, numbered chapters, parameter reference |
| `pdf/style.css`                         | page layout and colours                                                                     |
| `pdf/fonts/`                            | Barlow Semi Condensed ([SIL Open Font License](pdf/fonts/OFL.txt))                          |

For a new version of a guide, raise `version` and add a line to `revisions` in its front
matter. Chapters (`#`) and sections (`##`) are numbered in the PDF; refer to them as
"section 3.3".
