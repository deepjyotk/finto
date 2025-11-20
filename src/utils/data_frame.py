def _df_to_dict_safe(df):
    """Helper to safely convert DataFrame to a dict (records)."""
    if df is None:
        return {}
    if isinstance(df, dict):
        return df
    if hasattr(df, "to_dict"):
        return df.to_dict(orient="records")
    return {}
