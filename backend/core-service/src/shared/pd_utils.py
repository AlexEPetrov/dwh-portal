from typing import Dict

import numpy as np
import pandas as pd


def add_pct_diff_columns(df):
    """Добавляет % для каждой существующей numeric-колонки"""

    # Make a copy to avoid SettingWithCopyWarning
    result = df.copy()

    # Get only numeric columns
    numeric_cols = df.select_dtypes(include=["number"]).columns

    # Iterate through numeric columns
    for i in range(1, len(numeric_cols)):
        current_col = numeric_cols[i]
        prev_col = numeric_cols[i - 1]

        # Calculate difference
        diff = df[current_col] - df[prev_col]

        # Calculate percentage difference
        pct_diff = (df[current_col] - df[prev_col]) / df[prev_col] * 100

        # Insert new column after current column
        col_position = result.columns.get_loc(current_col) + 1
        result.insert(col_position, f"{current_col}_diff", diff)
        col_position = result.columns.get_loc(current_col) + 1
        result.insert(col_position, f"{current_col}_diff_pct", pct_diff)

    return result


def add_pct_diff_rows(
    df,
    index_prefixes,
    uom: str,
    scenario_name: str,
    delivery_market: str,
    product: str | None = None,
):
    # Make a copy to avoid modifying original
    result = df.copy()

    # Get only numeric columns
    numeric_cols = df.select_dtypes(include=["number"]).columns

    # Create a row for differences
    diff_row = {col: np.nan for col in df.columns}

    # Create a row for percentage differences
    pct_diff_row = {col: np.nan for col in df.columns}

    # Calculate diff + percentage diff between consecutive numeric columns
    for i in range(1, len(numeric_cols)):
        current_col = numeric_cols[i]
        prev_col = numeric_cols[i - 1]

        # Calculate percentage difference
        diff = df[current_col] - df[prev_col]

        # Calculate percentage difference
        pct_diff = (df[current_col] - df[prev_col]) / df[prev_col] * 100
        # base_value_name = df["property_name"]

        # Store in the current column's position
        pct_diff_row[current_col] = pct_diff.values
        pct_diff_row["property_name"] = [x + " - изм., проц." for x in index_prefixes]
        pct_diff_row["uom"] = "%"
        pct_diff_row["scenario_name"] = scenario_name
        pct_diff_row["delivery_market"] = delivery_market
        pct_diff_row["index"] = [x + " - изм., проц." for x in index_prefixes]
        if product is not None:
            pct_diff_row["product"] = product

        diff_row[current_col] = diff.values
        diff_row["property_name"] = [x + " - изм." for x in index_prefixes]
        diff_row["uom"] = uom
        diff_row["scenario_name"] = scenario_name
        diff_row["delivery_market"] = delivery_market
        diff_row["index"] = [x + " - изм." for x in index_prefixes]
        if product is not None:
            diff_row["product"] = product

    # Convert to DataFrame and concatenate
    pct_diff_df = pd.DataFrame(pct_diff_row, index=[x + " - изм., проц." for x in index_prefixes])
    diff_df = pd.DataFrame(diff_row, index=[x + " - изм." for x in index_prefixes])

    # Combine with original
    return pd.concat([result, diff_df, pct_diff_df])


def create_ratio_row(
    df, row_index1, row_index2, custom_props: Dict, product: str | None = None
) -> pd.DataFrame:
    numeric_cols = df.select_dtypes(include="number").columns
    ratio_values = df[numeric_cols].iloc[row_index1] / df[numeric_cols].iloc[row_index2].replace(
        0, pd.NA
    )
    ratio_row = {**custom_props, **ratio_values.to_dict()}
    if product is not None:
        ratio_row["product"] = product
    return pd.DataFrame([ratio_row])


def create_multiplied_row(
    df, row_index1, div_value, custom_props: Dict, product: str | None = None
) -> pd.DataFrame:
    numeric_cols = df.select_dtypes(include="number").columns
    ratio_values = df[numeric_cols].iloc[row_index1] * div_value
    ratio_row = {**custom_props, **ratio_values.to_dict()}
    if product is not None:
        ratio_row["product"] = product
    return pd.DataFrame([ratio_row])
