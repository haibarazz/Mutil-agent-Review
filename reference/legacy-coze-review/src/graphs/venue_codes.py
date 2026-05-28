"""期刊/会议代码枚举定义

前端根据 GraphInput 的 Literal 类型自动生成下拉选择框。
"""

# ===== CCF-A 会议/期刊（CS 领域） =====
CCFA_CODES = [
    "AAAI", "ACL", "ACM_MM", "ACM_SIGOPS_ATC_USENIX_ATC", "AI",
    "ASE", "ASPLOS", "Bioinformatics", "CAV", "CCS",
    "CHI", "CRYPTO", "CSCW", "CVPR", "DAC",
    "EUROCRYPT", "EuroSys", "FAST", "FM", "FOCS",
    "FSE", "HPCA", "HPDC", "IANDC", "ICCV",
    "ICDE", "ICLR", "ICML", "ICSE", "IEEE_VIS",
    "IJCV", "IJHCS", "INFOCOM", "ISCA", "ISSTA",
    "JACM", "JMLR", "Journal_of_Cryptology", "JSAC", "LICS",
    "MICRO", "MobiCom", "NDSS", "NeurIPS", "NSDI",
    "OOPSLA", "OSDI", "PLDI", "POPL", "PPoPP",
    "Proc_IEEE", "RTSS", "SandP", "SC", "SCIS",
    "SICOMP", "SIGCOMM", "SIGGRAPH", "SIGIR", "SIGKDD",
    "SIGMOD", "SODA", "SOSP", "STOC", "TACO",
    "TC", "TCAD", "TDSC", "TIFS", "TIP",
    "TIT", "TKDE", "TMC", "TMM", "TOCHI",
    "TOCS", "TODS", "TOG", "TOIS", "TON",
    "TOPLAS", "TOS", "TOSEM", "TPAMI", "TPDS",
    "TSC", "TSE", "TVCG", "UbiComp", "UIST",
    "USENIX_Security", "VLDB", "VLDBJ", "VR", "WWW",
]

# ===== UTD24 / FT50 期刊（IS 领域） =====
UTD_FT50_CODES = [
    "AER", "AMJ", "AMR", "AoMAnnals", "AOS",
    "ASQ", "ASR", "CAR", "ECMA", "ETP",
    "HBR", "HRM", "IJOC", "ISR", "JAE",
    "JAMS", "JAP", "JAR", "JBV", "JCP",
    "JCR", "JF", "JFE", "JFQA", "JIBS",
    "JM", "JMIS", "JMR", "JMS", "JOMgt",
    "JOMOps", "JPE", "MISQ", "MKS", "MS",
    "MSOM", "OBHDP", "OR", "OrgSci", "POM",
    "PsychSci", "QJE", "RAST", "REStud", "RFS",
    "ROF", "RP", "SEJ", "SMJ", "SMR",
    "TAR",
]

ALL_VENUE_CODES: list[str] = [""] + CCFA_CODES + UTD_FT50_CODES
