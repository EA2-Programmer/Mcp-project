def build_batch_tasks_query(limit: int, where_clause: str) -> str:
    return f"""
        SELECT TOP {limit}
            t.ID                        AS task_id,
            t.BatchID                   AS batch_id,
            b.Name                      AS batch_name,
            td.Name                     AS task_name,
            td.Description              AS task_description,
            t.[User]                    AS assigned_operator,
            t.PassFail                  AS pass_fail,
            CASE t.PassFail
                WHEN  1 THEN 'Completed'
                WHEN -1 THEN 'Incomplete'
                ELSE        'Pending'
            END                         AS status,
            t.Capture01                 AS sample_category,
            t.Capture02                 AS is_compulsory,
            t.Capture03                 AS is_retentive,
            t.Capture04                 AS requires_analysis,
            CONVERT(varchar(50), t.CreatedDateTime, 127)   AS created_at,
            CONVERT(varchar(50), t.CompletedDateTime, 127) AS completed_at,
            DATEDIFF(
                SECOND,
                t.CreatedDateTime,
                t.CompletedDateTime
            )                           AS completion_seconds,
            s.Name                      AS system_name,
            p.Name                      AS product_name
        FROM tTask t
        LEFT JOIN tTaskDefinition td ON t.TaskDefinitionID = td.ID
        INNER JOIN tBatch b          ON t.BatchID          = b.ID
        LEFT JOIN tSystem s          ON b.SystemID         = s.ID
        LEFT JOIN tJob j             ON b.JobID            = j.ID
        LEFT JOIN tProduct p         ON j.ProductID        = p.ID
        WHERE {where_clause}
        ORDER BY t.CreatedDateTime DESC
    """


def build_compliance_by_task_query(limit: int, where_clause: str) -> str:
    return f"""
        SELECT TOP {limit}
            td.Name                             AS task_name,
            td.Description                      AS task_description,
            COUNT(*)                            AS total_assignments,
            SUM(CASE WHEN t.PassFail =  1 THEN 1 ELSE 0 END) AS completed_count,
            SUM(CASE WHEN t.PassFail = -1 THEN 1 ELSE 0 END) AS incomplete_count,
            SUM(CASE WHEN t.PassFail NOT IN (1,-1) THEN 1 ELSE 0 END) AS pending_count,
            ROUND(
                100.0 * SUM(CASE WHEN t.PassFail = 1 THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0),
                1
            )                                   AS compliance_rate_pct
        FROM tTask t
        LEFT JOIN tTaskDefinition td ON t.TaskDefinitionID = td.ID
        INNER JOIN tBatch b          ON t.BatchID          = b.ID
        LEFT JOIN tSystem s          ON b.SystemID         = s.ID
        LEFT JOIN tJob j             ON b.JobID            = j.ID
        LEFT JOIN tProduct p         ON j.ProductID        = p.ID
        WHERE {where_clause}
        GROUP BY td.Name, td.Description
        ORDER BY incomplete_count DESC, total_assignments DESC
    """


def build_compliance_totals_query(where_clause: str) -> str:
    return f"""
        SELECT
            COUNT(*)                                          AS total_tasks,
            SUM(CASE WHEN t.PassFail =  1 THEN 1 ELSE 0 END) AS total_completed,
            SUM(CASE WHEN t.PassFail = -1 THEN 1 ELSE 0 END) AS total_incomplete,
            COUNT(DISTINCT t.BatchID)                         AS batches_covered
        FROM tTask t
        INNER JOIN tBatch b  ON t.BatchID   = b.ID
        LEFT JOIN tSystem s  ON b.SystemID  = s.ID
        LEFT JOIN tJob j     ON b.JobID     = j.ID
        LEFT JOIN tProduct p ON j.ProductID = p.ID
        WHERE {where_clause}
    """