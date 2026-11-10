-- dart_periodic — 정기보고서(사업·반기·분기) 목록·원문·목차 공용 저장소
-- 규약은 ipo_db.cf_filing* / sr_filing_toc 와 같다 (docs/02-데이터저장.md)
CREATE DATABASE IF NOT EXISTS dart_periodic CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE dart_periodic;

CREATE TABLE IF NOT EXISTS pr_corp (
  corp_code   char(8)      NOT NULL COMMENT 'DART 고유번호',
  corp_name   varchar(200) DEFAULT NULL,
  stock_code  varchar(6)   DEFAULT NULL COMMENT '종목코드 (상폐는 공란일 수 있음)',
  modify_date varchar(8)   DEFAULT NULL,
  fetched_at  timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (corp_code),
  KEY ix_corp_stock (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='DART 기업고유번호 (corpCode.xml)';

CREATE TABLE IF NOT EXISTS pr_corp_collect (
  corp_code    char(8)    NOT NULL,
  bgn_de       varchar(8) NOT NULL COMMENT 'list.json 조회 시작 접수일',
  end_de       varchar(8) NOT NULL,
  n_rows       int        DEFAULT NULL,
  collected_at timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (corp_code, bgn_de, end_de)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='목록 수집 이력 (재실행 시 건너뛰기)';

CREATE TABLE IF NOT EXISTS pr_filing (
  rcept_no         varchar(14)  NOT NULL COMMENT '접수번호',
  corp_code        char(8)      NOT NULL,
  corp_name        varchar(200) DEFAULT NULL,
  stock_code       varchar(6)   DEFAULT NULL,
  report_nm        varchar(500) DEFAULT NULL COMMENT '보고서명 원문 ([기재정정] 등 접두어 포함)',
  rcept_dt         varchar(8)   DEFAULT NULL COMMENT '접수일자 YYYYMMDD',
  flr_nm           varchar(200) DEFAULT NULL,
  rm               varchar(200) DEFAULT NULL,
  doc_class        enum('annual','semi','quarter','other') NOT NULL,
  period_end       date         DEFAULT NULL COMMENT '보고서명 "(YYYY.MM)" 의 말일',
  rev_kind         enum('original','content','attach','other') DEFAULT NULL,
  is_body_version  tinyint(1)   NOT NULL DEFAULT 0 COMMENT '(회사,종류,기준일) 안에서 본문을 담은 버전. 목록 단계 잠정 → 원문 후 확정',
  xml_status       enum('ok','missing','error') DEFAULT NULL,
  html_status      enum('ok','error','no_viewer') DEFAULT NULL,
  toc_status       enum('ok','error','no_viewer') DEFAULT NULL COMMENT '뷰어 목차 수집 결과',
  origin           varchar(40)  NOT NULL DEFAULT 'opendart' COMMENT 'opendart | ipo_db.cf_filing',
  created_at       timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (rcept_no),
  KEY ix_pf_corp (corp_code, doc_class, period_end),
  KEY ix_pf_stock (stock_code),
  KEY ix_pf_rcpt (rcept_dt),
  KEY ix_pf_xml (xml_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='정기공시 목록';

CREATE TABLE IF NOT EXISTS pr_filing_xml (
  rcept_no        varchar(14)  NOT NULL,
  file_seq        smallint     NOT NULL COMMENT 'ZIP 순번(0부터). HTML 트랙은 toc_no',
  file_name       varchar(300) DEFAULT NULL,
  source          enum('xml','html') NOT NULL DEFAULT 'xml',
  is_main         tinyint(1)   NOT NULL DEFAULT 0 COMMENT '1=정기보고서 본문, 0=첨부(감사보고서 등)',
  encoding_used   varchar(20)  DEFAULT NULL,
  formula_version varchar(10)  DEFAULT NULL,
  title_cnt       smallint     DEFAULT NULL COMMENT '절 제목(<TITLE>) 수',
  raw_bytes       int          DEFAULT NULL,
  body_gz         longblob COMMENT '원문(UTF-8) gzip',
  origin          varchar(40)  NOT NULL DEFAULT 'opendart',
  created_at      timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (rcept_no, file_seq),
  KEY ix_px_main (is_main)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='정기보고서 원문 (gzip)';

CREATE TABLE IF NOT EXISTS pr_filing_toc (
  rcept_no      varchar(14)  NOT NULL,
  toc_no        smallint     NOT NULL COMMENT '뷰어 목차 노드 번호 (1부터)',
  level         tinyint      NOT NULL COMMENT '1=part 2=section-1 3=section-2',
  parent_toc_no smallint     DEFAULT NULL,
  title         varchar(300) DEFAULT NULL,
  dcm_no        varchar(20)  DEFAULT NULL COMMENT 'viewer.do dcmNo',
  ele_id        int          DEFAULT NULL COMMENT 'viewer.do eleId',
  offset        int          DEFAULT NULL,
  length        int          DEFAULT NULL,
  dtd           varchar(20)  DEFAULT NULL,
  created_at    timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (rcept_no, toc_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='DART 뷰어 목차 트리 (main.do)';

CREATE TABLE IF NOT EXISTS pr_fs_value (
  rcept_no   varchar(14)  NOT NULL,
  fs_scope   enum('consolidated','separate') NOT NULL,
  item       varchar(40)  NOT NULL COMMENT 'equity_total | equity_parent | equity_nci',
  value_won  bigint       DEFAULT NULL COMMENT '원 단위로 환산한 값',
  unit_text  varchar(40)  DEFAULT NULL COMMENT '원문 단위 표기 (단위 : 원 / 천원 / 백만원)',
  raw_text   varchar(300) DEFAULT NULL COMMENT '원문 행 텍스트',
  toc_no     smallint     DEFAULT NULL COMMENT '값이 실린 뷰어 목차 노드',
  extracted_at timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (rcept_no, fs_scope, item)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='원문 재무상태표에서 뽑은 값';

CREATE TABLE IF NOT EXISTS pr_capture (
  rcept_no    varchar(14)  NOT NULL,
  toc_no      smallint     NOT NULL,
  item        varchar(40)  NOT NULL,
  viewer_url  varchar(500) DEFAULT NULL,
  image_path  varchar(300) DEFAULT NULL COMMENT 'low-pbr/site/ 기준 상대경로',
  captured_at timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (rcept_no, toc_no, item)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='DART 뷰어 캡처';
