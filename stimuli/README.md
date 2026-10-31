# Provisional face stimuli

This is a temporary development set, not the participant's LISTA A archive and not a validated research stimulus set.

- Ten real photographs: nine distinct identity groups from `serengil/deepface` test photographs and one from `ageitgey/face_recognition` (Obama). Distinct groups in the first source follow its `master.csv` identity pairs. These include recognisable public figures; familiarity, image dimensions, demographics and photographic conditions are not matched.
- Ten AI-generated faces from David Beniaguev's **Synthetic Faces High Quality (SFHQ)** sample sheet, https://github.com/SelfishGene/SFHQ-dataset. The source documents StyleGAN2-based synthesis. These are synthetic identities, not face-swap videos. The internal `deepfake` label denotes the synthetic condition here.
- The original SFHQ sheet is retained unchanged. The feed displays ten separate 440×440 regions (first eight tiles, then first two tiles of the second row), excluding source labels and borders. Regions are cropped into cached WebP display derivatives on the server. No faces are regenerated or retouched; the common display pipeline resizes to at most 960 px and encodes at quality 92 while retaining originals. OLD presentations use the same derivatives as phase 1.
- `sources.json` records exact source commits, paths, classes and tile coordinates. Upstream MIT license notices are retained alongside it; those repository licenses do not establish model releases or clearance of every underlying photograph for participant research. Review source image rights and suitability before recruitment.
- Every post uses neutral account names, no source/category caption, no stimulus-based avatar, no prefilled comments and identical initial like counts. Stories are empty to avoid extra exposures before feed presentation. The order is shuffled per session and retained across interactions. It is not counterbalanced across participants and no persistent assignment database is configured.

The source metadata is for researchers. It is not displayed as a real/synthetic label in the participant interface.

## Recognition-only lures

`posts.json` also contains `recognition_new_posts`, excluded from phase 1: five additional photographs from the MIT-licensed `ageitgey/face_recognition` examples (Alex Lacamoire, Lin-Manuel Miranda, Joe Biden, Kit Harington and Rose Leslie), and five previously unused SFHQ source-sheet tiles (second row, columns 3–7). Exact source paths, commits and regions are recorded in `sources.json`. These ten identities are distinct from the phase-1 set. Their familiarity and image conditions are not experimentally matched.

The recognition task samples five old real and five old synthetic faces from phase 1, then shuffles them with these ten lures. Recognition cards use generic labels, not the original account names or reaction counts. No class or correctness feedback is displayed to participants.
