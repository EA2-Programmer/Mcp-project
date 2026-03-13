SYSTEM_NAME_LOOKUP = """
    SELECT TOP 1 ID
    FROM tSystem
    WHERE Name = ? OR AltName = ? OR ExternalID = ?
"""

OEE_METRICS = """
    SELECT
        SUM(DATEDIFF(MINUTE, StartDateTime, ISNULL(EndDateTime, GETDATE()))) AS total_runtime_mins,
        COUNT(ID) AS session_count
    FROM tJobSystemActual
    WHERE SystemID = ?
      AND StartDateTime >= ?
      AND (EndDateTime <= ? OR EndDateTime IS NULL)
"""

# Tag columns and joins are conditional — only added when include_tags=True
TAG_COLUMNS = """,
    t_act.Value   AS actual_count,   t_act.Units AS count_units,
    t_prod.Value  AS current_product,
    t_batch.Value AS current_batch,
    t_plan.Value  AS planned_count
"""

TAG_JOINS = """
    LEFT JOIN tTag t_act   ON s.ActualSizeTagID  = t_act.ID
    LEFT JOIN tTag t_prod  ON s.ProductTagID     = t_prod.ID
    LEFT JOIN tTag t_batch ON s.BatchTagID       = t_batch.ID
    LEFT JOIN tTag t_plan  ON s.PlannedSizeTagID = t_plan.ID
"""


def build_equipment_state_query(limit: int, where_clause: str, include_tags: bool) -> str:
    tag_columns = TAG_COLUMNS if include_tags else ""
    tag_joins = TAG_JOINS if include_tags else ""
    return f"""
        SELECT TOP {limit}
            s.ID          AS system_id,
            s.Name        AS system_name,
            s.Description,
            s.AreaID,
            jsa.JobID     AS current_job_id,
            jsa.StartDateTime AS session_start,
            CASE WHEN jsa.ID IS NOT NULL THEN 'Running' ELSE 'Idle' END AS status
            {tag_columns}
        FROM tSystem s
        LEFT JOIN tJobSystemActual jsa
            ON s.ID = jsa.SystemID
            AND jsa.EndDateTime IS NULL
        {tag_joins}
        WHERE {where_clause}
        ORDER BY s.DisplayOrder
    """