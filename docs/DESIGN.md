# Daily Practices Collector - 상세 설계안

## 1. 프로젝트 개요

### 1.1 배경
Data Platform 팀에서 AI-Ready Data 서비스를 준비하는 과정에서, 전사적인 Agentic AI 개발 니즈에
대응하기 위해 StarRocks/Spark 관련 Best Practice 사례를 자동 수집하고 리포트를 생성하는 시스템.

### 1.2 목표
- 하루 1회 자동으로 StarRocks, Spark, Iceberg, Data Lakehouse 관련 BP 사례 수집
- Baidu, Alibaba, GitHub, GeekNews 등 다양한 소스에서 크롤링
- 중복 제거 후 상세 리포트 자동 생성
- 팀원 및 사용자에게 Slack/Email 등으로 배포

### 1.3 대상 기술 키워드
| 카테고리 | 키워드 |
|---------|--------|
| Core | StarRocks, Apache Spark, Apache Iceberg |
| Lakehouse | Data Lakehouse, Polaris Catalog, Table Format |
| AI/ML | AI-Ready Data, Feature Store, Vector Database |
| Infra | Kubernetes Data Platform, S3 Data Lake |
| Analytics | Superset, OLAP, Real-time Analytics |
| 참조사례 | Baidu Data Platform, Alibaba Data Lake, ByteDance |

---

## 2. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                    Scheduler (APScheduler/Cron)          │
│                    매일 09:00 KST 실행                    │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  Source Collectors Layer                  │
│                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ GitHub   │ │ GeekNews │ │ Tech Blog│ │ RSS/Atom  │  │
│  │ Collector│ │ Collector│ │ Crawler  │ │ Collector │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘  │
│       │             │            │              │        │
│  ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ ┌─────┴─────┐  │
│  │ HN/Reddit│ │ Medium/  │ │ arXiv    │ │ YouTube   │  │
│  │ Collector│ │ Dev.to   │ │ Collector│ │ Collector │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘  │
└───────┴─────────────┴────────────┴─────────────┴────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Processing Pipeline                         │
│                                                          │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ Normalizer │→ │ Deduplicator │→ │ Content Enricher│  │
│  │ (정규화)    │  │ (중복제거)    │  │ (요약/분류)      │  │
│  └────────────┘  └──────────────┘  └─────────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Storage Layer (SQLite + JSON)                │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ articles DB │  │ hash_index   │  │ reports/       │  │
│  │ (SQLite)    │  │ (중복체크)    │  │ (Markdown/HTML)│  │
│  └─────────────┘  └──────────────┘  └────────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Report Generator                            │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ LLM Summarizer│ │ Markdown     │ │ HTML Template │  │
│  │ (Claude API) │  │ Generator    │ │ Renderer      │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Distribution Layer                          │
│                                                          │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌──────────────┐  │
│  │ Slack  │  │ Email  │  │ GitHub │  │ Static Site  │  │
│  │ Webhook│  │ SMTP   │  │ Pages  │  │ (optional)   │  │
│  └────────┘  └────────┘  └────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 수집 소스 상세

### 3.1 GitHub Sources

| 소스 | 수집 방법 | 수집 대상 |
|------|----------|----------|
| GitHub Trending | GitHub API + scraping | StarRocks/Spark 관련 trending repos |
| GitHub Releases | GitHub API (REST) | starrocks/starrocks, apache/spark 릴리즈 |
| GitHub Discussions | GraphQL API | 주요 repo의 discussions/issues |
| Awesome Lists | Raw content API | awesome-starrocks, awesome-spark 등 |
| GitHub Stars | API search | 신규 star 급상승 프로젝트 |

**API 사용 예시:**
```python
# GitHub Search API - StarRocks 관련 최신 레포 검색
GET /search/repositories?q=starrocks+pushed:>2026-03-11&sort=stars
GET /search/repositories?q=spark+lakehouse+pushed:>2026-03-11&sort=stars

# GitHub Releases
GET /repos/StarRocks/starrocks/releases?per_page=5
GET /repos/apache/spark/releases?per_page=5
```

### 3.2 Tech News / Blog Sources

| 소스 | URL | 수집 방법 |
|------|-----|----------|
| GeekNews (긱뉴스) | https://news.hada.io | RSS + HTML scraping |
| Hacker News | https://news.ycombinator.com | Algolia API (HN Search) |
| Reddit | r/dataengineering, r/apachespark | Reddit API (PRAW) |
| dev.to | dev.to/t/starrocks, dev.to/t/spark | RSS Feed |
| Medium | medium.com/tag/starrocks | RSS Feed |
| DZone | dzone.com | RSS Feed |
| InfoQ | infoq.com | RSS Feed |

### 3.3 기업 기술 블로그 (중국 기업 포함)

| 기업 | 블로그 URL | 관련성 |
|------|-----------|--------|
| Baidu Tech | tech.baidu.com | StarRocks 주요 사용사 |
| Alibaba Tech | developer.aliyun.com/blog | Data Lake/Iceberg 사례 |
| ByteDance | blog.bytedance.com | 대규모 데이터 처리 사례 |
| Meituan Tech | tech.meituan.com | StarRocks 실시간분석 사례 |
| JD Tech | blog.jd.com | 이커머스 데이터 파이프라인 |
| StarRocks Blog | www.starrocks.io/blog | 공식 블로그 |
| Databricks Blog | databricks.com/blog | Spark/Lakehouse BP |
| Cloudera Blog | blog.cloudera.com | Spark/Iceberg 사례 |
| Tabular Blog | tabular.io/blog | Iceberg 사례 |

### 3.4 기타 소스

| 소스 | 설명 |
|------|------|
| arXiv | 데이터 레이크하우스/OLAP 관련 논문 |
| YouTube | 컨퍼런스 발표 (Data+AI Summit, StarRocks Summit 등) |
| SlideShare/SpeakerDeck | 기술 발표 자료 |
| WeChat Official Accounts | 중국 기술 커뮤니티 (선택적) |

---

## 4. 핵심 컴포넌트 상세 설계

### 4.1 Collector Base Class

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class CollectedArticle:
    """수집된 아티클의 표준 데이터 모델"""
    title: str
    url: str
    source: str                    # "github", "hackernews", "geeknews", ...
    source_type: str               # "repository", "article", "discussion", ...
    content_snippet: str           # 본문 요약 또는 첫 500자
    full_content: Optional[str]    # 전체 본문 (가능한 경우)
    author: Optional[str]
    published_at: Optional[datetime]
    collected_at: datetime = field(default_factory=datetime.utcnow)
    tags: list[str] = field(default_factory=list)
    relevance_score: float = 0.0   # 0.0~1.0 관련성 점수
    language: str = "en"           # "en", "zh", "ko"
    metadata: dict = field(default_factory=dict)  # 소스별 추가 데이터

class BaseCollector(ABC):
    """모든 Collector의 기본 클래스"""

    def __init__(self, config: dict):
        self.config = config
        self.keywords = config.get("keywords", [])
        self.max_items = config.get("max_items_per_source", 50)

    @abstractmethod
    async def collect(self) -> list[CollectedArticle]:
        """소스에서 아티클을 수집하여 반환"""
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        pass

    def calculate_relevance(self, article: CollectedArticle) -> float:
        """키워드 매칭 기반 관련성 점수 계산"""
        score = 0.0
        text = f"{article.title} {article.content_snippet}".lower()
        for keyword in self.keywords:
            if keyword.lower() in text:
                score += 0.2
        return min(score, 1.0)
```

### 4.2 중복 제거 (Deduplication) 전략

3단계 중복 제거를 적용합니다:

```
┌──────────────────────────────────────────────┐
│          Stage 1: URL Exact Match            │
│  - URL 정규화 후 exact match                  │
│  - query params 제거, trailing slash 통일     │
│  - 가장 빠르고 확실한 중복 체크               │
└──────────────────┬───────────────────────────┘
                   │ 통과
                   ▼
┌──────────────────────────────────────────────┐
│       Stage 2: Content Hash (SimHash)        │
│  - 제목+본문 기반 SimHash 생성                │
│  - Hamming distance 3 이내 = 중복 판정        │
│  - 같은 내용 다른 URL (재게시/번역) 탐지      │
└──────────────────┬───────────────────────────┘
                   │ 통과
                   ▼
┌──────────────────────────────────────────────┐
│     Stage 3: Semantic Similarity (선택)       │
│  - Sentence Transformer embedding             │
│  - Cosine similarity > 0.92 = 중복 의심       │
│  - 의역/재작성 컨텐츠 탐지                    │
│  - 비용 고려하여 선택적 적용                   │
└──────────────────────────────────────────────┘
```

**SQLite 스키마 (중복 체크용):**
```sql
CREATE TABLE IF NOT EXISTS article_hashes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_normalized TEXT UNIQUE NOT NULL,
    content_simhash TEXT NOT NULL,
    title_hash TEXT NOT NULL,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source TEXT NOT NULL
);

CREATE INDEX idx_simhash ON article_hashes(content_simhash);
CREATE INDEX idx_title_hash ON article_hashes(title_hash);
```

### 4.3 LLM 기반 콘텐츠 요약 및 분류

Claude API를 활용하여 수집된 아티클을 요약하고 분류합니다:

```python
SUMMARIZE_PROMPT = """
당신은 Data Platform 팀의 기술 리서처입니다.
아래 아티클을 분석하여 JSON 형식으로 응답하세요.

팀 컨텍스트:
- 환경: k8s + Iceberg + Polaris + DataHub + Spark + StarRocks + S3
- 목표: AI-Ready Data 서비스 구축
- 사용자: Superset/StarRocks/Spark 기반 분석

아티클:
제목: {title}
URL: {url}
본문: {content}

응답 형식:
{{
  "summary_ko": "3-5문장 한국어 요약",
  "summary_en": "3-5 sentence English summary",
  "category": "StarRocks|Spark|Iceberg|Lakehouse|AI-Data|Infrastructure|Other",
  "relevance_to_team": "high|medium|low",
  "key_takeaways": ["핵심 포인트 1", "핵심 포인트 2", ...],
  "applicable_scenarios": ["우리 팀에 적용 가능한 시나리오"],
  "tech_stack_overlap": ["StarRocks", "Spark", ...],
  "difficulty": "beginner|intermediate|advanced"
}}
"""
```

### 4.4 리포트 생성 구조

일일 리포트는 다음 구조로 생성됩니다:

```
reports/
├── 2026-03-12/
│   ├── daily-report.md          # 메인 Markdown 리포트
│   ├── daily-report.html        # HTML 렌더링 버전
│   ├── raw-articles.json        # 수집된 원본 데이터
│   └── summary-stats.json       # 통계 데이터
```

**리포트 Markdown 템플릿:**
```markdown
# Daily Data Platform Practices Report
📅 {date} | 수집 건수: {total_count}건 | 신규: {new_count}건

---

## 🔥 Today's Highlights
{top_3_articles_with_high_relevance}

## 📊 StarRocks Best Practices
### 새로운 사례
{starrocks_articles}

### 릴리즈 & 업데이트
{starrocks_releases}

## ⚡ Spark & Lakehouse
### Best Practices
{spark_articles}

### Iceberg / Table Format 동향
{iceberg_articles}

## 🤖 AI-Ready Data
{ai_data_articles}

## 🏢 기업 사례 (Baidu, Alibaba, ByteDance 등)
{enterprise_cases}

## 🌟 GitHub Trending
| Repo | Stars | 설명 |
|------|-------|------|
{github_trending_table}

## 📈 통계
- 전체 수집: {total_count}건
- 중복 제거: {dedup_count}건
- 소스별: GitHub({github_count}), GeekNews({geeknews_count}), ...
- 카테고리별: StarRocks({sr_count}), Spark({spark_count}), ...

---
*Generated by Daily Practices Collector v1.0*
*다음 수집: {next_run_time}*
```

---

## 5. 데이터베이스 스키마

```sql
-- 메인 아티클 테이블
CREATE TABLE articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    url_normalized TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    source_type TEXT NOT NULL,
    content_snippet TEXT,
    full_content TEXT,
    author TEXT,
    language TEXT DEFAULT 'en',
    published_at TIMESTAMP,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    relevance_score REAL DEFAULT 0.0,
    content_simhash TEXT,

    -- LLM 분석 결과
    summary_ko TEXT,
    summary_en TEXT,
    category TEXT,
    relevance_to_team TEXT,
    key_takeaways TEXT,  -- JSON array
    difficulty TEXT,

    -- 메타데이터
    metadata TEXT  -- JSON
);

-- 태그 테이블
CREATE TABLE article_tags (
    article_id INTEGER REFERENCES articles(id),
    tag TEXT NOT NULL,
    PRIMARY KEY (article_id, tag)
);

-- 일일 리포트 테이블
CREATE TABLE daily_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date DATE UNIQUE NOT NULL,
    total_collected INTEGER DEFAULT 0,
    new_articles INTEGER DEFAULT 0,
    dedup_removed INTEGER DEFAULT 0,
    report_path TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 수집 로그
CREATE TABLE collection_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collector_name TEXT NOT NULL,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    items_collected INTEGER DEFAULT 0,
    items_new INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',  -- pending, running, success, failed
    error_message TEXT
);

CREATE INDEX idx_articles_date ON articles(collected_at);
CREATE INDEX idx_articles_category ON articles(category);
CREATE INDEX idx_articles_source ON articles(source);
CREATE INDEX idx_articles_relevance ON articles(relevance_score DESC);
```

---

## 6. 프로젝트 디렉토리 구조

```
Starrocks-report/
├── docs/
│   └── DESIGN.md                    # 이 문서
├── src/
│   ├── __init__.py
│   ├── main.py                      # 엔트리포인트, 스케줄러
│   ├── config.py                    # 설정 관리
│   │
│   ├── collectors/                  # 소스별 수집기
│   │   ├── __init__.py
│   │   ├── base.py                  # BaseCollector, CollectedArticle
│   │   ├── github_collector.py      # GitHub API 수집
│   │   ├── hackernews_collector.py  # HN Algolia API
│   │   ├── geeknews_collector.py    # 긱뉴스 수집
│   │   ├── rss_collector.py         # RSS/Atom 피드 수집
│   │   ├── techblog_collector.py    # 기업 기술 블로그
│   │   └── reddit_collector.py      # Reddit API
│   │
│   ├── processing/                  # 데이터 처리
│   │   ├── __init__.py
│   │   ├── normalizer.py            # URL/텍스트 정규화
│   │   ├── deduplicator.py          # 3단계 중복 제거
│   │   ├── enricher.py              # LLM 기반 요약/분류
│   │   └── relevance.py             # 관련성 점수 계산
│   │
│   ├── report/                      # 리포트 생성
│   │   ├── __init__.py
│   │   ├── generator.py             # Markdown 리포트 생성
│   │   ├── html_renderer.py         # HTML 변환
│   │   └── templates/
│   │       ├── daily_report.md.j2   # Jinja2 템플릿
│   │       └── daily_report.html.j2
│   │
│   ├── distribution/                # 배포
│   │   ├── __init__.py
│   │   ├── slack_notifier.py        # Slack 알림
│   │   ├── email_sender.py          # 이메일 발송
│   │   └── github_publisher.py      # GitHub Pages 배포
│   │
│   ├── storage/                     # 저장소
│   │   ├── __init__.py
│   │   ├── database.py              # SQLite 관리
│   │   └── file_store.py            # 파일 기반 저장
│   │
│   └── utils/                       # 유틸리티
│       ├── __init__.py
│       ├── http_client.py           # aiohttp 래퍼 (rate limiting)
│       ├── simhash.py               # SimHash 구현
│       └── logger.py                # 로깅 설정
│
├── config/
│   ├── config.yaml                  # 메인 설정
│   ├── sources.yaml                 # 수집 소스 목록
│   └── keywords.yaml                # 키워드 설정
│
├── reports/                         # 생성된 리포트 저장
│   └── .gitkeep
│
├── data/                            # SQLite DB, 캐시
│   └── .gitkeep
│
├── tests/
│   ├── __init__.py
│   ├── test_collectors.py
│   ├── test_deduplicator.py
│   └── test_report_generator.py
│
├── Dockerfile
├── docker-compose.yaml
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## 7. 설정 파일 상세

### 7.1 config.yaml
```yaml
app:
  name: "daily-practices-collector"
  version: "1.0.0"
  timezone: "Asia/Seoul"

schedule:
  cron: "0 9 * * *"       # 매일 오전 9시 KST
  retry_on_failure: true
  max_retries: 3

collection:
  max_items_per_source: 50
  request_timeout: 30       # seconds
  rate_limit_delay: 1.0     # seconds between requests
  concurrent_collectors: 5
  lookback_hours: 26        # 약간의 오버랩으로 누락 방지

deduplication:
  url_normalization: true
  simhash_threshold: 3      # hamming distance
  enable_semantic: false     # 초기에는 비활성화

enrichment:
  llm_provider: "anthropic"
  llm_model: "claude-sonnet-4-6"
  max_articles_to_summarize: 30    # 비용 관리
  min_relevance_for_summary: 0.3

report:
  output_dir: "./reports"
  format: ["markdown", "html"]
  max_highlights: 5
  include_stats: true

distribution:
  slack:
    enabled: false
    webhook_url: "${SLACK_WEBHOOK_URL}"
    channel: "#data-platform-news"
  email:
    enabled: false
    smtp_host: ""
    recipients: []

storage:
  db_path: "./data/articles.db"
  keep_days: 90             # 90일 이후 자동 삭제
```

### 7.2 keywords.yaml
```yaml
# 우선순위별 키워드 그룹
primary:
  - StarRocks
  - Apache Spark
  - Apache Iceberg
  - Data Lakehouse

secondary:
  - Polaris Catalog
  - DataHub metadata
  - Superset dashboard
  - OLAP analytics
  - real-time analytics

tertiary:
  - AI-ready data
  - feature store
  - vector database
  - data mesh
  - data fabric
  - Kubernetes data platform

enterprise:
  - Baidu data platform
  - Alibaba data lake
  - ByteDance data
  - Meituan StarRocks
  - JD data pipeline
  - 百度 StarRocks          # 중국어 키워드
  - 阿里巴巴 数据湖

negative:
  - job posting
  - hiring
  - recruitment
  - salary
```

### 7.3 sources.yaml
```yaml
github:
  repositories:
    - StarRocks/starrocks
    - apache/spark
    - apache/iceberg
    - apache/polaris
    - apache/superset
    - linkedin/datahub
  search_queries:
    - "starrocks best practice"
    - "spark lakehouse iceberg"
    - "data lakehouse architecture"
  trending:
    languages: ["python", "java", "scala", "go"]
    since: "daily"

rss_feeds:
  - name: "StarRocks Blog"
    url: "https://www.starrocks.io/blog/rss"
    category: "starrocks"
  - name: "Databricks Blog"
    url: "https://www.databricks.com/feed"
    category: "spark"
  - name: "dev.to StarRocks"
    url: "https://dev.to/feed/tag/starrocks"
    category: "starrocks"
  - name: "dev.to Spark"
    url: "https://dev.to/feed/tag/apachespark"
    category: "spark"
  - name: "InfoQ Data"
    url: "https://feed.infoq.com/data"
    category: "general"

hackernews:
  search_queries:
    - "StarRocks"
    - "Apache Spark"
    - "Data Lakehouse"
    - "Apache Iceberg"
  min_points: 5

geeknews:
  enabled: true
  keywords_filter: true

reddit:
  subreddits:
    - dataengineering
    - apachespark
    - Database
  min_upvotes: 10

tech_blogs:
  - name: "Alibaba Cloud Blog"
    url: "https://www.alibabacloud.com/blog"
    scrape_method: "html"
  - name: "Meituan Tech"
    url: "https://tech.meituan.com"
    scrape_method: "html"
    language: "zh"
```

---

## 8. 실행 흐름 (Sequence)

```
[09:00 KST] Scheduler 트리거
       │
       ▼
[1] 설정 로드 (config.yaml, sources.yaml, keywords.yaml)
       │
       ▼
[2] 수집기 병렬 실행 (asyncio.gather)
    ├── GitHub Collector      → 20~50 items
    ├── HackerNews Collector  → 10~30 items
    ├── GeekNews Collector    → 5~20 items
    ├── RSS Collector         → 20~40 items
    ├── TechBlog Collector    → 10~30 items
    └── Reddit Collector      → 10~20 items
       │
       ▼
[3] 수집 결과 통합 (~100~200 raw items)
       │
       ▼
[4] 정규화 (URL, 텍스트 클리닝)
       │
       ▼
[5] 중복 제거
    ├── Stage 1: URL exact match  → ~30% 제거
    ├── Stage 2: SimHash          → ~10% 추가 제거
    └── (선택) Stage 3: Semantic  → ~5% 추가 제거
       │
       ▼
[6] 관련성 점수 계산 & 정렬
       │
       ▼
[7] LLM 요약 (상위 30건만, 비용 관리)
    └── Claude API → 요약, 분류, 핵심 포인트
       │
       ▼
[8] DB 저장 (SQLite)
       │
       ▼
[9] 리포트 생성
    ├── Markdown 리포트
    └── HTML 리포트
       │
       ▼
[10] 배포
    ├── Slack 알림 (선택)
    ├── Email 발송 (선택)
    └── GitHub Pages (선택)
       │
       ▼
[11] 로그 기록 & 완료
```

---

## 9. 비용 & 리소스 추정

### 9.1 API 비용 (일일)
| 항목 | 추정 사용량 | 비용 |
|------|-----------|------|
| GitHub API | ~200 calls/day | 무료 (5000/hr 한도) |
| HN Algolia API | ~10 calls/day | 무료 |
| Claude API (요약) | ~30건 × ~2K tokens | ~$0.50/day |
| **합계** | | **~$0.50/day (~$15/month)** |

### 9.2 인프라
| 항목 | 사양 | 비용 |
|------|-----|------|
| 실행 환경 | Docker container (256MB RAM) | 기존 k8s 활용 시 무료 |
| 스토리지 | SQLite + 리포트 파일 (~10MB/month) | 무시 가능 |
| GitHub Actions (대안) | 10min/day | 무료 tier 내 |

---

## 10. 배포 옵션

### Option A: Kubernetes CronJob (권장)
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: daily-practices-collector
  namespace: data-platform
spec:
  schedule: "0 0 * * *"  # UTC 00:00 = KST 09:00
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: collector
            image: registry.internal/daily-practices-collector:latest
            envFrom:
            - secretRef:
                name: collector-secrets
            volumeMounts:
            - name: data
              mountPath: /app/data
            - name: reports
              mountPath: /app/reports
          volumes:
          - name: data
            persistentVolumeClaim:
              claimName: collector-data-pvc
          - name: reports
            persistentVolumeClaim:
              claimName: collector-reports-pvc
          restartPolicy: OnFailure
```

### Option B: GitHub Actions
```yaml
name: Daily Practices Collector
on:
  schedule:
    - cron: '0 0 * * *'  # UTC 00:00
  workflow_dispatch:       # 수동 실행 가능

jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python -m src.main
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      - uses: actions/upload-artifact@v4
        with:
          name: daily-report-${{ github.run_id }}
          path: reports/
```

---

## 11. 향후 확장 계획

### Phase 1 (MVP) - 2주
- [x] GitHub, HN, RSS 수집기 구현
- [x] URL 기반 중복 제거
- [x] Markdown 리포트 생성
- [x] CLI 수동 실행

### Phase 2 - 2주
- [ ] LLM 요약 통합 (Claude API)
- [ ] SimHash 중복 제거
- [ ] Slack 알림
- [ ] GitHub Actions 자동화

### Phase 3 - 2주
- [ ] 기업 기술 블로그 크롤러 (중국 기업 포함)
- [ ] HTML 리포트 + 정적 사이트
- [ ] 주간/월간 트렌드 분석 리포트
- [ ] 사용자 피드백 수집 (유용도 평가)

### Phase 4 (고급)
- [ ] Semantic dedup (sentence-transformers)
- [ ] 팀 내 지식 그래프 구축
- [ ] StarRocks에 수집 데이터 적재 → Superset 대시보드
- [ ] Agentic AI 연동 (수집 데이터를 RAG 소스로 활용)
