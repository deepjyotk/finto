def _df_to_dict_safe(df):
    """Helper to safely convert DataFrame to a dict (records)."""
    if df is None:
        return {}
    if isinstance(df, dict):
        return df
    if hasattr(df, "to_dict"):
        # Convert column names to strings to handle Timestamp columns
        df_copy = df.copy()
        df_copy.columns = [str(col) for col in df_copy.columns]
        return df_copy.to_dict(orient="records")
    return {}
