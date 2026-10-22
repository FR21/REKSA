export type Language = 'id' | 'en'

export interface TranslationSchema {
  common: {
    language: string
    languageSelect: string
    search: string
    filter: string
    all: string
    loading: string
    error: string
    errorSubtitle: string
    retry: string
    save: string
    saving: string
    cancel: string
    delete: string
    edit: string
    view: string
    action: string
    status: string
    online: string
    offline: string
    standby: string
    safe: string
    moderate: string
    high: string
    critical: string
    systemOperational: string
    lastSync: string
    close: string
    confirm: string
    exportCsv: string
    page: string
    of: string
    prev: string
    next: string
    showingRange: (start: number, end: number, total: number, item?: string) => string
    prevPageAria: string
    nextPageAria: string
    noData: string
    viewAll: string
    details: string
    active: string
  }
  nav: {
    overview: string
    live: string
    nearMiss: string
    workers: string
    settings: string
    brandSubtitle: string
    footerSystem: string
    footerDesc: string
    devicesOnline: string
  }
  pageTitles: {
    overview: string
    live: string
    nearMiss: string
    workers: string
    settings: string
    workerDetail: string
  }
  notifications: {
    title: string
    clearAll: string
    empty: string
    incidentAlert: string
    viewDetails: string
    tooltip: string
  }
  profileModal: {
    title: string
    fullName: string
    fullNamePlaceholder: string
    role: string
    save: string
    saving: string
    cancel: string
    tooltip: string
    roles: {
      supervisor: string
      manager: string
      officer: string
      operations: string
      admin: string
    }
  }
  overview: {
    eyebrow: string
    welcome: (name: string) => string
    subtitle: string
    criticalActive: (count: number) => string
    openLive: string
    nearHazard: (worker: string, hazard: string) => string
    kpiActiveWorkers: string
    kpiActiveWorkersDetail: (total: number) => string
    kpiActiveHazards: string
    kpiActiveHazardsDetail: string
    kpiHighRisk: string
    kpiHighRiskDetail: string
    kpiCriticalRisk: string
    kpiCriticalRiskDetail: string
    kpiNearMissToday: string
    kpiNearMissTodayDetail: string
    kpiAvgRisk: string
    kpiAvgRiskDetail: string
    kpiConnectedDevices: string
    kpiConnectedDevicesDetail: (percent: number) => string
    kpiWarningLatency: string
    kpiWarningLatencyDetail: string
    panelWorkerRisk: string
    panelWorkerRiskSub: string
    panelWorkerRiskEmpty: string
    panelWorkerRiskEmptySub: string
    panelTrend: string
    panelTrendSub: string
    panelDistribution: string
    panelDistributionSub: string
    panelActivity: string
    panelActivitySub: string
    activityEmpty: string
    activityNearMiss: string
    activityWarning: string
    activityInvestigation: string
    activityVoice: string
    activitySafe: string
    activityDefault: string
    activityMessages: Record<string, string>
    chartAvgRisk: string
    chartNearMiss: string
  }
  live: {
    eyebrow: string
    title: string
    desc: string
    searchPlaceholder: string
    filterAllRisk: string
    filterSafe: string
    filterModerate: string
    filterHigh: string
    filterCritical: string
    filterAllDevices: string
    filterOnlineHelmet: string
    filterOffline: string
    showing: (shown: number, total: number) => string
    empty: string
    cardRiskScore: string
    cardHazardNearby: string
    cardNoHazard: string
    cardDistance: string
    cardSignal: string
    cardArea: string
    cardTemp: string
    cardAir: string
    cardBuzzerTest: string
    cardBuzzerTesting: string
    cardMarkSafe: string
    cardMarkAllSafe: (count: number) => string
    cardBuzzerTestAll: (count: number) => string
    cardViewProfile: string
    criticalAlertTitle: string
    buzzerSuccess: string
    buzzerFailed: string
  }
  nearMisses: {
    eyebrow: string
    title: string
    desc: string
    loading: string
    searchPlaceholder: string
    filterAllRisk: string
    filterCritical: string
    filterHigh: string
    filterModerate: string
    filterAllStatus: string
    filterPending: string
    filterAcknowledged: string
    kpiTotal: string
    kpiTotalDetail: string
    kpiPending: string
    kpiPendingDetail: string
    kpiVerified: string
    kpiVerifiedDetail: string
    kpiCritical: string
    kpiCriticalDetail: string
    colTime: string
    colId: string
    colWorker: string
    colHazard: string
    colSignalDuration: string
    colRisk: string
    colStatus: string
    colAction: string
    sensorBleTrigger: string
    durationSec: (sec: number | string) => string
    statusVerified: string
    statusPending: string
    btnChangeNote: string
    btnTakeAction: string
    btnDetail: string
    empty: string
    modalTitle: string
    modalIncidentId: string
    modalTime: string
    modalWorker: string
    modalHazard: string
    supervisorLabel: string
    noteLabel: string
    notePlaceholder: string
    btnSave: string
    btnSaving: string
    toastSuccess: string
    errorConfirm: string
    itemUnit: string
    defaultNote: (hazard: string, type: string, worker: string) => string
  }
  workers: {
    eyebrow: string
    title: string
    desc: string
    kpiTotal: string
    kpiTotalDetail: string
    kpiHelmets: string
    kpiHelmetsOffline: (count: number) => string
    kpiAvgRisk: string
    kpiStatusCritical: string
    kpiStatusWarning: string
    kpiStatusControlled: string
    panelTitle: string
    panelSubtitle: string
    searchPlaceholder: string
    colWorker: string
    colRole: string
    colArea: string
    colDevice: string
    colStatus: string
    colAction: string
    rowClickTooltip: string
    noHelmet: string
    actionMenuTooltip: string
    menuEdit: string
    menuDelete: string
    confirmDelete: (name: string, id: string) => string
    formRegisterTitle: string
    formRegisterDesc: string
    formEditTitle: string
    formEditDesc: (name: string, id: string) => string
    labelId: string
    labelIdPlaceholder: string
    btnUseSuggestedId: (id: string) => string
    suggestedIdPlaceholder: (id: string) => string
    tooltipUseSuggestedId: string
    labelName: string
    labelNamePlaceholder: string
    labelRole: string
    labelArea: string
    btnRegister: string
    btnRegistering: string
    btnSaveEdit: string
    btnSaving: string
    addNewRole: string
    addNewArea: string
    rolePlaceholder: string
    areaPlaceholder: string
    btnSaveAndUse: string
    itemUnit: string
    toastCreated: string
    toastUpdated: string
    toastDeleted: string
    requiredFields: string
    empty: string
  }
  workerDetail: {
    back: string
    title: string
    shiftActive: (time: string) => string
    deviceOffline: string
    testBuzzer: string
    testBuzzerSending: string
    testBuzzerSuccess: string
    testBuzzerFailed: string
    currentRiskScore: string
    smartHelmet: string
    nearestHazard: string
    environment: string
    airQuality: string
    impact: string
    impactNormal: string
    impactHit: string
    impactFall: string
    signalRssi: string
    actionTitle: string
    actionSubtitle: string
    actionCritical: string
    actionHigh: string
    actionModerate: string
    actionSafe: string
    actionRecommendations: Record<string, string>
    dataSource: string
    auditTitle: string
    auditSubtitle: string
    auditEmpty: string
    auditVerified: string
    auditVerifiedSub: string
    auditPending: string
    auditPendingSub: string
    auditCritical: string
    auditCriticalSub: string
    auditSource: string
    riskFactorTitle: string
    riskFactorSubtitle: string
    factorLabels: Record<string, string>
    riskHistoryTitle: string
    riskHistorySubtitle: string
    nearMissHistoryTitle: string
    nearMissHistorySubtitle: (count: number) => string
    nearMissEmpty: string
    colTimestamp: string
    colHazard: string
    colRssi: string
    colDuration: string
    colRisk: string
    colDangerLevel: string
    colStatus: string
    btnAcknowledge: string
    verifiedK3: string
    itemUnit: string
  }
  settings: {
    eyebrow: string
    title: string
    desc: string
    tabProximity: string
    tabSensors: string
    tabRegistry: string
    warningBannerTitle: string
    warningBannerDesc: string
    sectionGasTitle: string
    sectionGasDesc: string
    fieldHeatWarning: string
    fieldHeatDanger: string
    fieldMqNormal: string
    fieldMqModerate: string
    fieldMqPoor: string
    sectionImpactTitle: string
    sectionImpactDesc: string
    fieldImpactWarning: string
    fieldImpactCritical: string
    fieldFallFreefall: string
    profileMobileTitle: string
    profileMobileDesc: string
    profileStationaryTitle: string
    profileStationaryDesc: string
    criticalDistance: string
    highWarning: string
    moderatePerimeter: string
    confirmCheckbox: string
    btnSaveThreshold: string
    btnSavingThreshold: string
    panelRegistryTitle: string
    panelRegistrySubtitle: (filtered: number, total: number) => string
    filterAllTypes: string
    filterHelmet: string
    filterHazardMobile: string
    filterHazardStationary: string
    filterEnvironment: string
    btnRefresh: string
    btnRefreshing: string
    refreshTooltip: string
    emptyDevices: string
    colDeviceId: string
    colType: string
    colLinkedTarget: string
    colStatus: string
    colLastSeen: string
    colAction: string
    formRegisterTitle: string
    formEditTitle: string
    formRegisterDesc: string
    formEditDesc: string
    labelDeviceType: string
    optHelmet: string
    optMobile: string
    optStationary: string
    optEnvironment: string
    labelSelectWorker: string
    labelSelectMobile: string
    labelSelectStationary: string
    labelSelectArea: string
    btnOpenCreator: string
    btnCloseCreator: string
    btnOpenStationaryCreator: string
    btnOpenPairModal: string
    btnPairRegister: string
    btnPairProcessing: string
    btnSaveDevice: string
    itemUnit: string
    confirmDeleteDevice: (id: string) => string
    creatorTitle: (category: string) => string
    creatorMachineType: string
    creatorUnitNum: string
    creatorDescriptiveName: string
    creatorLocationArea: string
    addNewArea: string
    areaPlaceholder: string
    btnSaveAndUse: string
    creatorBtnSave: string
    creatorBtnSaving: string
    firmwareBeaconStandard: string
    firmwareCopyTooltip: string
    firmwareHelmetNote: string
    firmwareMobileNote: string
    firmwareStationaryNote: string
    unifiedBindingTitle: string
    tileHelmetTitle: string
    tileHelmetDesc: string
    tileMobileTitle: string
    tileMobileDesc: string
    tileStationaryTitle: string
    tileStationaryDesc: string
    labelHardwareId: string
    labelAssignment: string
    autoConfigured: string
    readyToPair: string
    toggleManualConfig: string
    toggleManualConfigHide: string
    labelHardwareIdHelp: string
    langSettingLabel: string
    langSettingDesc: string
    savedMessage: string
    confirmThresholdMessage: string
  }
  voice: {
    panelTitle: string
    panelSubtitle: string
    btnShowHistory: (count: number) => string
    btnHideHistory: string
    feedbackSuccess: string
    feedbackAlarmSent: string
    emptyTitle: string
    emptyDesc: string
    transmittedAt: (time: string) => string
    transcriptionTitle: string
    nluAccuracy: (pct: number) => string
    btnPlayAudio: string
    btnPauseAudio: string
    simulatedAudio: string
    audioSpecs: (available: boolean) => string
    detectedEntities: string
    relatedHazard: string
    location: string
    classification: string
    actionRecommendation: string
    btnSendAlarm: string
    btnMarkHandled: string
    statusHandled: string
    statusWaiting: string
    historyTitle: (count: number) => string
    btnAcknowledge: string
    acknowledgedBy: (name: string) => string
    playAudio: string
  }
  aiAdvisory: {
    title: string
    subtitle: string
    awaitingInference: string
    factorsPrefix: string
    sourceTitle: string
    statusCollecting: string
    statusAwaiting: string
    statusUnavailable: string
    statusPhysical: string
    calibrated: string
    uncalibrated: string
    safetyRuleActive: string
    deviceOffline: string
    factorLabels: Record<string, string>
  }
}
