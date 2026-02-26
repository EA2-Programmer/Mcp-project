"""
SQL query templates for batch-related service functions.

UNDER CONSTRUCTION TRYING TO FIGURE OUT HOW TO MOVE THE SQL'S HERE


All queries are defined as constants here and imported by
services/batches.py. This keeps SQL readable and separated
from Python logic without file I/O overhead.

Note: {where_clause} and {safe_limit} are the only interpolated
values — both are controlled internally, never from user input.
"""

# Using .format() style - this is correct Python syntax
GET_BATCHES_SQL = """
    SELECT TOP {safe_limit}
        b.ID,
        b.Name,
        b.AltName,
        b.SystemID,
        b.JobID,
        b.Lot,
        b.SubLot,
        b.State,
        CAST(b.StartDateTime AS datetime) AS StartDateTime,
        CAST(b.EndDateTime AS datetime) AS EndDateTime,
        b.Date,
        b.PlannedBatchSize,
        b.ActualBatchSize,
        b.[User],
        j.Name AS JobName,
        j.ExternalID AS JobExternalID,
        p.Name AS ProductName,
        p.Description AS ProductDescription,
        s.Name AS SystemName
    FROM tBatch b
    LEFT JOIN tJob j ON b.JobID = j.ID
    LEFT JOIN tJobBatch     
    LEFT JOIN tProduct p ON j.ProductID = p.ID
    LEFT JOIN tSystem s ON b.SystemID = s.ID
    WHERE {where_clause}
    ORDER BY b.StartDateTime DESC
"""

GET_BATCH_PARAMETERS_SQL = """
        SELECT TOP {safe_limit}
            bp.ID                       AS parameter_id,
            bp.BatchID                  AS batch_id,
            b.Name                      AS batch_name,
            b.Lot                       AS batch_lot,
            b.SubLot                    AS batch_sublot,
            pd.Name                     AS parameter_name,
            pd.Description              AS parameter_description,
            bp.Value                    AS value_raw,
            TRY_CAST(bp.Value AS float) AS value_numeric,
            pd.MinimumValue             AS min_allowed,
            pd.MaximumValue             AS max_allowed,
            bp.ModifiedDateTime         AS recorded_at,
            b.StartDateTime             AS batch_start,
            b.EndDateTime               AS batch_end,
            CASE WHEN TRY_CAST(bp.Value AS float) IS NOT NULL
                 AND (TRY_CAST(bp.Value AS float) < pd.MinimumValue
                      OR TRY_CAST(bp.Value AS float) > pd.MaximumValue)
                 THEN 1 ELSE 0 END      AS is_deviation
        FROM tBatchParameter bp
        INNER JOIN tBatch b
            ON bp.BatchID = b.ID
        INNER JOIN tParameterDefinition pd
            ON bp.ParameterDefinitionID = pd.ID
        WHERE {where_clause}
        ORDER BY b.StartDateTime DESC, pd.DisplayOrder, bp.ModifiedDateTime DESC
    """




GET_BATCH_MATERIALS_SQL = """
    SELECT TOP {safe_limit}
        mua.ID AS material_use_id,
        mua.JobID AS job_id,
        b.Name AS batch_name,
        b.Lot AS batch_lot,
        b.SubLot AS batch_sublot,
        mat.Name AS material_name,
        mat.MaterialCode AS material_code,
        mat.Units AS units,
        mua.Quantity AS consumed_quantity,
        mua.DateTime AS consumption_datetime,
        b.StartDateTime AS batch_start,
        b.EndDateTime AS batch_end
    FROM tMaterialUseActual mua
    INNER JOIN tBatch b ON mua.JobID = b.JobID
    INNER JOIN tMaterial mat ON mua.MaterialID = mat.ID
    WHERE {where_clause}
    ORDER BY b.StartDateTime DESC, mua.DateTime DESC
"""