    USE [EBR_Template]
GO

INSERT INTO [dbo].[tOeeCalculation] (
    [ID], [Guid], [IsTemplate], [TemplateParentID], [Name], [AltName], [Description], [Notes],
    [SystemID], [Key], [OeeCalculationTypeID], [IntervalSeconds], [IntervalSyncMidnightOffsetSeconds],
    [TheoreticalCalculationUnitsPerMinuteSourceType], [TheoreticalCalculationUnitsPerMinuteSource],
    [TheoreticalCalculationUnitsPerMinuteConstant], [TheoreticalCalculationUnitsPerMinuteTagID],
    [TargetRateSourceType], [TargetRateSource], [TargetRateConstant], [TargetRateTagID], [TargetRateUnitType],
    [EstimateJobEndMinimumMinutes], [EstimateJobEndMinRateMultiplier], [EstimateJobEndMaxRateMultiplier],
    [CalculationUnits], [CalculationUnitsMeasureID], [DisplayUnits], [DisplayUnitsMeasureID],
    [DisplayUnitsDivisorSourceType], [DisplayUnitsDivisorSource], [DisplayUnitsDivisorConstant],
    [DisplayUnitsDivisorTagID], [DerivedInput], [OeeCaptureSchemeID],
    [BaselineOee], [BaselineAvailability], [BaselinePerformance], [BaselineQuality], [BaselineTeep],
    [TargetOee], [TargetAvailability], [TargetPerformance], [TargetQuality], [TargetTeep],
    [UpdateIntervalMinutes], [SuppressCounts], [ScriptClassName], [Color], [ColorCss], [IconCss],
    [ViewInReports], [DisplayOrder], [Enabled], [IsReadOnly], [TemplateData], [ModifiedDateTime], [UploadedDateTime]
)
VALUES
-- Line E1 Configuration (SystemID 3)
(
    1, NEWID(), 0, NULL, 'OEE Config - Line E1', 'E1_OEE', 'Standard OEE Calculation for Line E1', 'Demo Golden Line',
    3, 'E1.OEE.CALC', NULL, 3600, 0, -- <== Changed from 1 to NULL here
    0, 'Constant', 100.0, NULL,
    0, 'Constant', 100.0, NULL, 1,
    0, 0.0, 0.0,
    'KGR', NULL, 'KGR', NULL,
    0, 'Constant', 1.0, NULL, 0, NULL,
    60.0, 60.0, 60.0, 60.0, 60.0,
    85.0, 90.0, 95.0, 99.0, 85.0,
    15, 0, '', NULL, '', '',
    1, 1, 1, 0, '', SYSDATETIMEOFFSET(), NULL
),
-- Line E2 Configuration (SystemID 5)
(
    2, NEWID(), 0, NULL, 'OEE Config - Line E2', 'E2_OEE', 'Standard OEE Calculation for Line E2', 'Demo Bottleneck Line',
    5, 'E2.OEE.CALC', NULL, 3600, 0, -- <== Changed from 1 to NULL here
    0, 'Constant', 100.0, NULL,
    0, 'Constant', 100.0, NULL, 1,
    0, 0.0, 0.0,
    'KGR', NULL, 'KGR', NULL,
    0, 'Constant', 1.0, NULL, 0, NULL,
    60.0, 60.0, 60.0, 60.0, 60.0,
    85.0, 90.0, 95.0, 99.0, 85.0,
    15, 0, '', NULL, '', '',
    1, 2, 1, 0, '', SYSDATETIMEOFFSET(), NULL
),
-- Line E3 Configuration (SystemID 6)
(
    3, NEWID(), 0, NULL, 'OEE Config - Line E3', 'E3_OEE', 'Standard OEE Calculation for Line E3', 'Demo Quality Issue Line',
    6, 'E3.OEE.CALC', NULL, 3600, 0, -- <== Changed from 1 to NULL here
    0, 'Constant', 100.0, NULL,
    0, 'Constant', 100.0, NULL, 1, 
    0, 0.0, 0.0, 
    'KGR', NULL, 'KGR', NULL, 
    0, 'Constant', 1.0, NULL, 0, NULL, 
    60.0, 60.0, 60.0, 60.0, 60.0, 
    85.0, 90.0, 95.0, 99.0, 85.0, 
    15, 0, '', NULL, '', '', 
    1, 3, 1, 0, '', SYSDATETIMEOFFSET(), NULL
);
GO


USE [EBR_Template]
GO

INSERT INTO [dbo].[tOeeInterval] (
    [ID], [OeeCalculationID], [StartDateTime], [EndDateTime], [Date],
    [ShiftHistoryID], [ProductID], [JobID],
    [Capture01], [Capture02], [Capture03], [Capture04], [Capture05],
    [Capture06], [Capture07], [Capture08], [Capture09], [Capture10],
    [TheoreticalCalculationUnitsPerMinute], [TargetCalculationUnitsPerMinute],
    [TotalCalculationUnitsCount], [TotalCalculationUnitsMultiplier],
    [GoodCalculationUnitsCount], [GoodCalculationUnitsMultiplier],
    [BadCalculationUnitsCount], [BadCalculationUnitsMultiplier], [DisplayUnitsDivisor],
    [AvailabilityLossSeconds], [SystemNotScheduledSeconds], [PerformanceLossSeconds], [LegalLossSeconds],
    [MtbfFailureCount], [MtbfFailureSeconds], [MtbfExcludedSeconds],
    [Seconds01], [Seconds02], [Seconds03], [Seconds04], [Seconds05],
    [Seconds06], [Seconds07], [Seconds08], [Seconds09], [Seconds10],
    [IsException], [IsEdited], [Notes], [ModifiedDateTime], [UploadedDateTime]
)
VALUES
-- ==========================================
-- SHIFT 1: 08:00 to 16:00 (Sample hour: 08:00 - 09:00)
-- ==========================================
-- E1: High Performance, High Quality
(1001, 1, '2026-03-12 08:00:00 +01:00', '2026-03-12 09:00:00 +01:00', '2026-03-12', NULL, 93, 1185, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 100.0, 100.0, 5800, 1.0, 5750, 1.0, 50, 1.0, 1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Shift 1 - Golden Run', SYSDATETIMEOFFSET(), NULL),
-- E2: Availability Issue (20 mins / 1200 sec downtime)
(1002, 2, '2026-03-12 08:00:00 +01:00', '2026-03-12 09:00:00 +01:00', '2026-03-12', NULL, 93, 1185, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 100.0, 100.0, 3800, 1.0, 3750, 1.0, 50, 1.0, 1.0, 1200, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Shift 1 - Heavy Downtime', SYSDATETIMEOFFSET(), NULL),
-- E3: Quality Issue (1000 bad units)
(1003, 3, '2026-03-12 08:00:00 +01:00', '2026-03-12 09:00:00 +01:00', '2026-03-12', NULL, 93, 1185, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 100.0, 100.0, 5900, 1.0, 4900, 1.0, 1000, 1.0, 1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Shift 1 - Quality Spike', SYSDATETIMEOFFSET(), NULL),

-- ==========================================
-- SHIFT 2: 16:00 to 22:00 (Sample hour: 16:00 - 17:00)
-- ==========================================
-- E1: High Performance, High Quality
(1004, 1, '2026-03-12 16:00:00 +01:00', '2026-03-12 17:00:00 +01:00', '2026-03-12', NULL, 93, 1185, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 100.0, 100.0, 5900, 1.0, 5800, 1.0, 100, 1.0, 1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Shift 2 - Steady Run', SYSDATETIMEOFFSET(), NULL),
-- E2: Availability Issue (25 mins / 1500 sec downtime)
(1005, 2, '2026-03-12 16:00:00 +01:00', '2026-03-12 17:00:00 +01:00', '2026-03-12', NULL, 93, 1185, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 100.0, 100.0, 3500, 1.0, 3400, 1.0, 100, 1.0, 1.0, 1500, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Shift 2 - Major Stoppage', SYSDATETIMEOFFSET(), NULL),
-- E3: Quality Issue (800 bad units)
(1006, 3, '2026-03-12 16:00:00 +01:00', '2026-03-12 17:00:00 +01:00', '2026-03-12', NULL, 93, 1185, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 100.0, 100.0, 5800, 1.0, 5000, 1.0, 800, 1.0, 1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Shift 2 - Quality Issues', SYSDATETIMEOFFSET(), NULL),

-- ==========================================
-- SHIFT 3: 22:00 to 08:00 (Sample hour: 22:00 - 23:00)
-- ==========================================
-- E1: High Performance, High Quality
(1007, 1, '2026-03-12 22:00:00 +01:00', '2026-03-12 23:00:00 +01:00', '2026-03-12', NULL, 93, 1185, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 100.0, 100.0, 5950, 1.0, 5900, 1.0, 50, 1.0, 1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Shift 3 - Optimal Run', SYSDATETIMEOFFSET(), NULL),
-- E2: Availability Issue (15 mins / 900 sec downtime)
(1008, 2, '2026-03-12 22:00:00 +01:00', '2026-03-12 23:00:00 +01:00', '2026-03-12', NULL, 93, 1185, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 100.0, 100.0, 4000, 1.0, 3950, 1.0, 50, 1.0, 1.0, 900, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Shift 3 - Minor Stoppages', SYSDATETIMEOFFSET(), NULL),
-- E3: Quality Issue (1500 bad units - Massive failure)
(1009, 3, '2026-03-12 22:00:00 +01:00', '2026-03-12 23:00:00 +01:00', '2026-03-12', NULL, 93, 1185, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 100.0, 100.0, 6000, 1.0, 4500, 1.0, 1500, 1.0, 1.0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 'Shift 3 - Critical Scrap Rate', SYSDATETIMEOFFSET(), NULL);
GO



USE [EBR_Template]
GO

-- =====================================================================
-- PART A: CREATE THE EVENT DEFINITIONS (Satisfies the Foreign Key)
-- =====================================================================
INSERT INTO [dbo].[tEventDefinition] (
    [ID], [Guid], [IsTemplate], [TemplateParentID], [Name], [AltName], [Description], [Notes],
    [SystemID], [SubSystemID], [EventDefinitionGroupID], [EventDefinitionTypeID], [Key],
    [TriggerWhenEquals], [TriggerTagID], [IgnoresSuppression], [EventCategoryID],
    [OeeEventType], [OeeEventTypeSecondsSourceType], [OeeEventTypeSecondsSource], [OeeEventTypeSecondsTagID],
    [OeeEventTypeSecondsConstant], [MtbfType], [ReEvaluateSystemEventOnStart], [ReEvaluateSystemEventOnEnd],
    [Priority], [SubPriority], [DurationSeconds], [ManualAllowInSummary], [ManualAllowInDetail],
    [EventIsolationType], [ScriptClassName], [ShowForAcknowledge], [DisplayDelaySeconds],
    [AcknowledgeDurationMinutes], [Color], [ColorCss], [IconCss], [ViewInReports], [DisplayOrder],
    [Enabled], [IsReadOnly], [TemplateData], [ModifiedDateTime], [UploadedDateTime]
)
VALUES
(
    101, NEWID(), 0, NULL, 'Motor Fault', 'MTR_FLT', 'Main drive motor overload tripped.', '',
    5, NULL, NULL, NULL, 'E2_MOTOR_FLT',
    1, NULL, 0, NULL,
    1, 0, 'Constant', NULL, 0, 1, 0, 0,
    1, 0, 0, 1, 1, 0, '', 0, 0, 0, NULL, '', '', 1, 1, 1, 0, '', SYSDATETIMEOFFSET(), NULL
),
(
    102, NEWID(), 0, NULL, 'Infeed Jam', 'INF_JAM', 'Severe jam at the infeed conveyor.', '',
    5, NULL, NULL, NULL, 'E2_INF_JAM',
    1, NULL, 0, NULL,
    1, 0, 'Constant', NULL, 0, 1, 0, 0,
    1, 0, 0, 1, 1, 0, '', 0, 0, 0, NULL, '', '', 1, 2, 1, 0, '', SYSDATETIMEOFFSET(), NULL
),
(
    103, NEWID(), 0, NULL, 'Sensor Failure', 'SNR_FLT', 'Optical sensor lost alignment.', '',
    5, NULL, NULL, NULL, 'E2_SNR_FLT',
    1, NULL, 0, NULL,
    1, 0, 'Constant', NULL, 0, 1, 0, 0,
    1, 0, 0, 1, 1, 0, '', 0, 0, 0, NULL, '', '', 1, 3, 1, 0, '', SYSDATETIMEOFFSET(), NULL
);
GO

-- =====================================================================
-- PART B: INSERT THE DOWNTIME EVENTS (Maps to our OEE intervals)
-- =====================================================================
INSERT INTO [dbo].[tEvent] (
    [ID], [StartDateTime], [EndDateTime], [Date], [Impact], [Count],
    [EventDefinitionID], [EventCategory01ID], [EventCategory02ID], [EventCategory03ID],
    [EventCategory04ID], [EventCategory05ID], [EventCategory06ID], [EventCategory07ID],
    [EventCategory08ID], [EventCategory09ID], [EventCategory10ID], [EventCodeID],
    [Capture01], [Capture02], [Capture03], [Capture04], [Capture05],
    [Capture06], [Capture07], [Capture08], [Capture09], [Capture10],
    [ShiftHistoryID], [ProductID], [JobID], [BatchID],
    [OeeEventType], [EventIsolationType], [State], [StateDateTime],
    [SplitEventID], [LinkedEventID], [DisplayDelaySeconds], [AcknowledgeDurationMinutes],
    [IsEdited], [User], [Notes], [ModifiedDateTime], [UploadedDateTime]
)
VALUES
-- Shift 1 EVENT: Motor Fault (1200 seconds / 20 mins)
(
    2001, '2026-03-12 08:15:00 +01:00', '2026-03-12 08:35:00 +01:00', '2026-03-12', 1200.0, 1,
    101, NULL, NULL, NULL, -- Set Category to NULL to prevent any hidden category FK errors
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, 93, 1185, NULL,
    1, 0, 0, '2026-03-12 08:35:00 +01:00',
    NULL, NULL, 0, 0,
    0, 'System', 'Main drive motor overload tripped.', SYSDATETIMEOFFSET(), NULL
),
-- Shift 2 EVENT: Infeed Jam (1500 seconds / 25 mins)
(
    2002, '2026-03-12 16:30:00 +01:00', '2026-03-12 16:55:00 +01:00', '2026-03-12', 1500.0, 1,
    102, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, 93, 1185, NULL,
    1, 0, 0, '2026-03-12 16:55:00 +01:00',
    NULL, NULL, 0, 0,
    0, 'Operator_John', 'Severe jam at the infeed conveyor, required manual clearing.', SYSDATETIMEOFFSET(), NULL
),
-- Shift 3 EVENT: Sensor Failure (900 seconds / 15 mins)
(
    2003, '2026-03-12 22:10:00 +01:00', '2026-03-12 22:25:00 +01:00', '2026-03-12', 900.0, 1,
    103, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, 93, 1185, NULL,
    1, 0, 0, '2026-03-12 22:25:00 +01:00',
    NULL, NULL, 0, 0,
    0, 'System', 'Optical sensor PE-404 lost alignment.', SYSDATETIMEOFFSET(), NULL
);
GO