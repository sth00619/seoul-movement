"""Seoul-movement-lecture data pipeline.

Public API:
    - src.ingest          — Stage 0 (API loaders)
    - src.mock_data       — offline data generator (matches API schema exactly)
    - src.preprocess      — Stages 1-2 (schema normalization + entity resolution)
    - src.features        — Stage 3 (6-feature engineering)
    - src.cluster         — Stage 4 (scaling + KMeans + UMAP)
    - src.lawd_codes      — legal-dong lookup + focus-station metadata
"""
