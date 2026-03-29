BATCH_NAME_LOOKUP = """
    SELECT TOP 1 ID
    FROM tBatch
    WHERE Name = ? OR AltName = ? OR Lot = ?
    ORDER BY StartDateTime DESC
"""

SYSTEM_NAME_LOOKUP = """
    SELECT TOP 1 ID
    FROM tSystem
    WHERE Name = ? AND IsTemplate = 0
"""

BATCH_JOB_LOOKUP = "SELECT TOP 1 JobID FROM tBatch WHERE ID = ?"


_BATCH_COLUMNS = """
    b.ID                                AS batch_id,
    b.Name                              AS batch_name,
    b.SystemID                          AS system_id,
    b.JobID                             AS job_id,
    b.State                             AS state,
    CONVERT(nvarchar(30), b.StartDateTime, 127) AS start_datetime,
    CONVERT(nvarchar(30), b.EndDateTime, 127) AS end_datetime,
    CONVERT(nvarchar(10), b.Date, 127)  AS batch_date,
    b.PlannedBatchSize                  AS planned_batch_size,
    b.ActualBatchSize                   AS actual_batch_size,
    b.PlannedBatchDurationSeconds       AS planned_duration_seconds,
    j.Name                              AS job_name,
    j.Lot                               AS job_lot,
    CONVERT(nvarchar(30), j.PlannedStartDateTime, 127) AS job_planned_start,
    jb.RecipeID                         AS recipe_id,
    jb.PlannedNumberOfBatches           AS planned_number_of_batches,
    jb.PlannedBatchSize                 AS job_planned_batch_size,
    CONVERT(nvarchar(10), jb.PlannedBatchSizeUnits) AS planned_batch_size_units,
    p.Name                              AS product_name,
    p.ProductCode                       AS product_code,
    p.Description                       AS product_description,
    s.Name                              AS system_name,
    sh.ID                               AS shift_history_id,
    sh.ShiftID                          AS shift_id,
    sh.TeamID                           AS team_id,
    CONVERT(nvarchar(30), sh.StartDateTime, 127) AS shift_start,
    CONVERT(nvarchar(30), sh.EndDateTime, 127) AS shift_end,
    CONVERT(nvarchar(10), sh.Date, 127) AS shift_date
"""

_BATCH_JOINS = """
    FROM tBatch b
    LEFT JOIN tJob          j   ON b.JobID          = j.ID
    LEFT JOIN tJobBatch     jb  ON b.JobID          = jb.JobID
    LEFT JOIN tProduct      p   ON j.ProductID      = p.ID
    LEFT JOIN tSystem       s   ON b.SystemID       = s.ID
    LEFT JOIN tShiftHistory sh  ON b.ShiftHistoryID = sh.ID
"""

_PARAMETER_COLUMNS = """
    bp.ID                       AS parameter_id,
    bp.BatchID                  AS batch_id,
    b.Name                      AS batch_name,
    pd.Name                     AS parameter_name,
    pd.Description              AS parameter_description,
    bp.Value                    AS value_raw,
    TRY_CAST(bp.Value AS float) AS value_numeric,
    pd.MinimumValue             AS min_allowed,
    pd.MaximumValue             AS max_allowed,
    CASE
        WHEN TRY_CAST(bp.Value AS float) IS NOT NULL
         AND (TRY_CAST(bp.Value AS float) < pd.MinimumValue
              OR TRY_CAST(bp.Value AS float) > pd.MaximumValue)
        THEN 1 ELSE 0
    END                         AS is_deviation
"""

_MATERIAL_COLUMNS = """
    mua.ID                      AS material_use_id,
    mua.JobID                   AS job_id,
    b.ID                        AS batch_id,
    b.Name                      AS batch_name,
    mat.Name                    AS material_name,
    mat.MaterialCode            AS material_code,
    mat.Units                   AS units,
    mua.Quantity                AS consumed_quantity
"""


# Query builders

def build_batches_query(limit: int, where_clause: str) -> str:
    return f"""
        SELECT TOP {limit}
        {_BATCH_COLUMNS}
        {_BATCH_JOINS}
        WHERE {where_clause}
        ORDER BY b.StartDateTime DESC
    """


def build_parameters_query(limit: int, where_clause: str) -> str:
    return f"""
        SELECT TOP {limit}
        {_PARAMETER_COLUMNS}
        FROM tBatchParameter bp
        INNER JOIN tBatch b             ON bp.BatchID = b.ID
        INNER JOIN tParameterDefinition pd ON bp.ParameterDefinitionID = pd.ID
        WHERE {where_clause}
        ORDER BY b.StartDateTime DESC, pd.DisplayOrder, bp.ModifiedDateTime DESC
    """


def build_materials_query(limit: int, where_clause: str) -> str:
    return f"""
        SELECT TOP {limit}
        {_MATERIAL_COLUMNS}
        FROM tMaterialUseActual mua
        INNER JOIN tBatch b      ON mua.JobID     = b.JobID
        INNER JOIN tMaterial mat ON mua.MaterialID = mat.ID
        WHERE {where_clause}
        ORDER BY mua.DateTime DESC
    """


# Static detail queries — no dynamic WHERE needed beyond batch_id param

BATCH_INFO = """
    SELECT
        b.ID                            AS batch_id,
        b.Name                          AS batch_name,
        b.JobID                         AS job_id,
        b.State                         AS state,
        CONVERT(nvarchar(30), b.StartDateTime, 127) AS start_datetime,
        CONVERT(nvarchar(30), b.EndDateTime, 127) AS end_datetime,
        b.PlannedBatchSize              AS planned_batch_size,
        b.ActualBatchSize               AS actual_batch_size,
        b.PlannedBatchDurationSeconds   AS planned_duration_seconds,
        ISNULL(CONVERT(nvarchar(100), b.[User]), '') AS operator,
        j.Name                          AS job_name,
        ISNULL(CONVERT(nvarchar(100), j.ExternalID), '') AS job_external_id,
        p.Name                          AS product_name,
        p.ProductCode                   AS product_code,
        p.Description                   AS product_description,
        s.Name                          AS system_name,
        ISNULL(CONVERT(nvarchar(100), s.ExternalID), '') AS system_external_id
    FROM tBatch b
    LEFT JOIN tJob     j ON b.JobID     = j.ID
    LEFT JOIN tProduct p ON j.ProductID = p.ID
    LEFT JOIN tSystem  s ON b.SystemID  = s.ID
    WHERE b.ID = ?
"""

BATCH_STEPS = """
    SELECT
        bs.ID                       AS step_id,
        bs.BatchID                  AS batch_id,
        CONVERT(nvarchar(30), bs.StartDateTime, 127) AS step_start,
        CONVERT(nvarchar(30), bs.EndDateTime, 127) AS step_end,
        bs.[User]                   AS step_operator,
        fd.Name                     AS step_name,
        fd.Description              AS step_description,
        DATEDIFF(SECOND, bs.StartDateTime, bs.EndDateTime) AS duration_seconds
    FROM tBatchStep bs
    LEFT JOIN tFunctionDefinition fd ON bs.FunctionDefinitionID = fd.ID
    WHERE bs.BatchID = ?
    ORDER BY bs.StartDateTime ASC
"""

# _DBR stores free-text remarks entered by operators during the batch
OPERATOR_REMARKS_BY_BATCH = """
    SELECT
        dbr.JobID               AS job_id,
        dbr.BatchStepID         AS batch_step_id,
        b.ID                    AS batch_id,
        b.Name                  AS batch_name,
        dbr.[User]              AS operator,
        dbr.RemarkNote          AS remark_text,
        CONVERT(varchar(50), dbr.datetime, 127) AS recorded_at
    FROM _DBR dbr
    INNER JOIN tBatchStep bs ON dbr.BatchStepID = bs.ID
    INNER JOIN tBatch b      ON bs.BatchID      = b.ID
    WHERE b.ID = ?
      AND dbr.RemarkNote IS NOT NULL
      AND dbr.culture = 'en-US'
    ORDER BY dbr.datetime ASC
"""

# PassFail: 1 = completed, -1 = incomplete/failed
COMPLIANCE_TASKS_BY_BATCH = """
    SELECT
        t.ID                        AS task_id,
        t.BatchID                   AS batch_id,
        td.Name                     AS task_name,
        td.Description              AS task_description,
        t.[User]                    AS assigned_operator,
        t.PassFail                  AS pass_fail,
        CASE t.PassFail
            WHEN  1 THEN 'Completed'
            WHEN -1 THEN 'Incomplete'
            ELSE 'Pending'
        END                         AS status,
        t.Capture01                 AS sample_category,
        t.Capture02                 AS is_compulsory,
        t.Capture03                 AS is_retentive,
        t.Capture04                 AS requires_analysis,
        CONVERT(varchar(50), t.CreatedDateTime, 127) AS created_at,
        CONVERT(varchar(50), t.CompletedDateTime, 127) AS completed_at
    FROM tTask t
    LEFT JOIN tTaskDefinition td ON t.TaskDefinitionID = td.ID
    WHERE t.BatchID = ?
    ORDER BY t.CreatedDateTime ASC
"""

# Quality analysis — three-signal queries with a shared batch filter

def build_quality_deviations_query(limit: int, batch_filter: str) -> str:
    return f"""
        SELECT TOP {limit}
            bp.BatchID                  AS batch_id,
            b.JobID                      AS job_id,
            b.Name                       AS batch_name,
            p.Name                       AS product_name,
            s.Name                       AS system_name,
            pd.Name                      AS parameter_name,
            pd.Description               AS parameter_description,
            bp.Value                     AS value_raw,
            TRY_CAST(bp.Value AS float)  AS value_numeric,
            pd.MinimumValue              AS min_allowed,
            pd.MaximumValue              AS max_allowed,
            b.StartDateTime              AS batch_start,
            b.EndDateTime                AS batch_end
        FROM tBatchParameter bp
        INNER JOIN tBatch b                ON bp.BatchID               = b.ID
        INNER JOIN tParameterDefinition pd ON bp.ParameterDefinitionID = pd.ID
        LEFT  JOIN tJob j                  ON b.JobID                  = j.ID
        LEFT  JOIN tProduct p              ON j.ProductID              = p.ID
        LEFT  JOIN tSystem s               ON b.SystemID               = s.ID
        WHERE {batch_filter}
          AND TRY_CAST(bp.Value AS float) IS NOT NULL
          AND (
              TRY_CAST(bp.Value AS float) < pd.MinimumValue
              OR TRY_CAST(bp.Value AS float) > pd.MaximumValue
          )
        ORDER BY b.StartDateTime DESC, pd.DisplayOrder
    """


def build_quality_remarks_query(limit: int, batch_filter: str) -> str:
    return f"""
        SELECT TOP {limit}
            dbr.JobID               AS job_id,
            b.ID                    AS batch_id,
            b.Name                  AS batch_name,
            p.Name                  AS product_name,
            s.Name                  AS system_name,
            dbr.[User]              AS operator,
            dbr.RemarkNote          AS remark_text,
            CONVERT(varchar(50), dbr.datetime, 127) AS recorded_at
        FROM _DBR dbr
        INNER JOIN tBatchStep bs ON dbr.BatchStepID = bs.ID
        INNER JOIN tBatch b      ON bs.BatchID      = b.ID
        LEFT  JOIN tJob j        ON b.JobID         = j.ID
        LEFT  JOIN tProduct p    ON j.ProductID     = p.ID
        LEFT  JOIN tSystem s     ON b.SystemID      = s.ID
        WHERE {batch_filter}
          AND dbr.RemarkNote IS NOT NULL
          AND dbr.culture = 'en-US'
        ORDER BY dbr.datetime DESC
    """


def build_quality_incomplete_tasks_query(limit: int, batch_filter: str) -> str:
    return f"""
        SELECT TOP {limit}
            t.BatchID               AS batch_id,
            b.JobID                 AS job_id,
            b.Name                  AS batch_name,
            p.Name                  AS product_name,
            s.Name                  AS system_name,
            td.Name                 AS task_name,
            td.Description          AS task_description,
            t.[User]                AS assigned_operator,
            t.Capture01             AS sample_category,
            t.Capture02             AS is_compulsory,
            t.Capture03             AS is_retentive,
            t.Capture04             AS requires_analysis,
            CONVERT(varchar(50), t.CreatedDateTime, 127) AS created_at,
            CONVERT(varchar(50), t.CompletedDateTime, 127) AS completed_at
        FROM tTask t
        LEFT  JOIN tTaskDefinition td ON t.TaskDefinitionID = td.ID
        INNER JOIN tBatch b           ON t.BatchID          = b.ID
        LEFT  JOIN tJob j             ON b.JobID            = j.ID
        LEFT  JOIN tProduct p         ON j.ProductID        = p.ID
        LEFT  JOIN tSystem s          ON b.SystemID         = s.ID
        WHERE {batch_filter}
          AND t.PassFail = -1
        ORDER BY t.CreatedDateTime DESC
    """


def build_planned_bom_raw_query(include_version: bool = False) -> str:
    version_clause = "AND bom.Version = ?" if include_version else ""
    return f"""
        SELECT
            bom.OpAc            AS operation_step,
            bom.Component       AS material_code,
            bom.BOMComponent    AS material_name,
            bom.Quantity        AS quantity,
            bom.Un              AS planned_unit
        FROM _SAPBOM bom
        WHERE bom.Material = ?
          {version_clause}
    """
