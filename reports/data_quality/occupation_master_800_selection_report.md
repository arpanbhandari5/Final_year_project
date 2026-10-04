# Occupation master 800 selection

BLS employment, projected employment, and annual openings were used only to rank **commonness** for sampling. They are not task-exposure labels.
Join: O*NET `occupation_code` first 7 characters == BLS `bls_matrix_code` for Line item rows. No fuzzy match.

- eligible occupations with ≥3 O*NET tasks: 923
- exact BLS-mapped eligible: 923
- written rows: 800 (unique codes 800); target 800; gate_exactly_800=True
- SOC major groups represented: 22
- stratum counts: {'employment_openings_70pct': 488, 'strategic_coverage_10pct': 177, 'soc_diversity_20pct': 135}
- SHA-256: `26eeee1a06e4919eaf699f7a9da2d0a5f417e625f4d968326ef12daec93c4aa5`

If `gate_exactly_800` is false, do not invent occupations to pad the list.
