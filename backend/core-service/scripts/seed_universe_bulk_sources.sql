-- Bulk lineage seeds for Universe stress (DATA_SOURCE → EXTRACTION_SOURCE → PROCESS).
-- Names are real/public data sources (open APIs, exchanges, gov open data) — demo only.
-- Schema: sol_dwh_portal. Idempotent. Tagged attributes.seed = 'universe_bulk'.
--
-- Usage (any SQL client / psql — no psql variables):
--   psql -h localhost -U postgres -d dwh -f scripts/seed_universe_bulk_sources.sql
--
-- To take fewer than the full catalog, change bulk_limit below (max = catalog size).
--
-- Cleanup:
--   DELETE FROM sol_dwh_portal.portal_relationships
--    WHERE attributes->>'seed' = 'universe_bulk'
--       OR from_asset_id IN (SELECT id FROM sol_dwh_portal.portal_assets
--                            WHERE attributes->>'seed' = 'universe_bulk')
--       OR to_asset_id   IN (SELECT id FROM sol_dwh_portal.portal_assets
--                            WHERE attributes->>'seed' = 'universe_bulk');
--   DELETE FROM sol_dwh_portal.portal_assets WHERE attributes->>'seed' = 'universe_bulk';
--
-- Note: collect --reset purges the whole portal snapshot, including these rows.

BEGIN;

DELETE FROM sol_dwh_portal.portal_relationships
WHERE from_asset_id IN (
        SELECT id FROM sol_dwh_portal.portal_assets
        WHERE attributes->>'seed' = 'universe_bulk'
      )
   OR to_asset_id IN (
        SELECT id FROM sol_dwh_portal.portal_assets
        WHERE attributes->>'seed' = 'universe_bulk'
      );

DELETE FROM sol_dwh_portal.portal_assets
WHERE attributes->>'seed' = 'universe_bulk';

WITH
params AS (
  -- how many catalog rows to seed (capped by catalog size later)
  SELECT 250::int AS n, now() AS ts, 'universe_bulk'::text AS provider
),
-- slug, display name, kind — гипотетический data_source_items.kind
-- (Котировки, Внутренний рынок, Экспорт, Производство, …)
catalog (ord, slug, title, kind) AS (
  VALUES
  (1,  'fred', 'FRED (St. Louis Fed)', 'Внутренний рынок'),
  (2,  'ecb-sdw', 'ECB Statistical Data Warehouse', 'Внутренний рынок'),
  (3,  'bis-stats', 'BIS Statistics', 'Внутренний рынок'),
  (4,  'imf-data', 'IMF Data', 'Внутренний рынок'),
  (5,  'world-bank', 'World Bank Open Data', 'Внутренний рынок'),
  (6,  'oecd-data', 'OECD Data', 'Внутренний рынок'),
  (7,  'eurostat', 'Eurostat', 'Внутренний рынок'),
  (8,  'ons-uk', 'ONS UK', 'Внутренний рынок'),
  (9,  'insee', 'INSEE', 'Внутренний рынок'),
  (10, 'destatis', 'Destatis', 'Внутренний рынок'),
  (11, 'istat', 'Istat', 'Внутренний рынок'),
  (12, 'cbr', 'Bank of Russia', 'Внутренний рынок'),
  (13, 'boj', 'Bank of Japan', 'Внутренний рынок'),
  (14, 'boe', 'Bank of England', 'Внутренний рынок'),
  (15, 'snb', 'Swiss National Bank', 'Внутренний рынок'),
  (16, 'riksbank', 'Riksbank', 'Внутренний рынок'),
  (17, 'nbp', 'Narodowy Bank Polski', 'Внутренний рынок'),
  (18, 'cnb', 'Czech National Bank', 'Внутренний рынок'),
  (19, 'mnb', 'Magyar Nemzeti Bank', 'Внутренний рынок'),
  (20, 'norges-bank', 'Norges Bank', 'Внутренний рынок'),
  (21, 'rba', 'Reserve Bank of Australia', 'Внутренний рынок'),
  (22, 'rbnz', 'Reserve Bank of New Zealand', 'Внутренний рынок'),
  (23, 'bank-canada', 'Bank of Canada', 'Внутренний рынок'),
  (24, 'bls', 'US BLS', 'Внутренний рынок'),
  (25, 'bea', 'US BEA', 'Внутренний рынок'),
  (26, 'census-bureau', 'US Census Bureau', 'Внутренний рынок'),
  (27, 'data-gov', 'Data.gov', 'Открытые данные'),
  (28, 'data-gov-uk', 'data.gov.uk', 'Открытые данные'),
  (29, 'data-gouv-fr', 'data.gouv.fr', 'Открытые данные'),
  (30, 'govdata-de', 'GovData.de', 'Открытые данные'),
  (31, 'datos-gob-es', 'datos.gob.es', 'Открытые данные'),
  (32, 'dati-gov-it', 'dati.gov.it', 'Открытые данные'),
  (33, 'opendata-swiss', 'opendata.swiss', 'Открытые данные'),
  (34, 'data-gov-sg', 'data.gov.sg', 'Открытые данные'),
  (35, 'data-gov-au', 'data.gov.au', 'Открытые данные'),
  (36, 'data-canada', 'Open Government Canada', 'Открытые данные'),
  (37, 'eu-opendata', 'data.europa.eu', 'Открытые данные'),
  (38, 'who-gho', 'WHO Global Health Observatory', 'Открытые данные'),
  (39, 'unicef-data', 'UNICEF Data', 'Открытые данные'),
  (40, 'un-comtrade', 'UN Comtrade', 'Экспорт'),
  (41, 'wto-stats', 'WTO Stats', 'Экспорт'),
  (42, 'faostat', 'FAOSTAT', 'Открытые данные'),
  (43, 'iloistat', 'ILOSTAT', 'Открытые данные'),
  (44, 'our-world-in-data', 'Our World in Data', 'Открытые данные'),
  (45, 'gapminder', 'Gapminder', 'Открытые данные'),
  (46, 'eia', 'US EIA', 'Производство'),
  (47, 'entsoe', 'ENTSO-E Transparency', 'Производство'),
  (48, 'acer', 'ACER REMIT', 'Производство'),
  (49, 'gie-agsi', 'GIE AGSI+', 'Производство'),
  (50, 'gie-alsi', 'GIE ALSI', 'Производство'),
  (51, 'entsog', 'ENTSOG TP', 'Производство'),
  (52, 'nord-pool', 'Nord Pool', 'Производство'),
  (53, 'epex-spot', 'EPEX SPOT', 'Производство'),
  (54, 'eex', 'EEX', 'Производство'),
  (55, 'ice', 'ICE', 'Котировки'),
  (56, 'cme', 'CME Group', 'Котировки'),
  (57, 'nymex', 'NYMEX', 'Котировки'),
  (58, 'comex', 'COMEX', 'Котировки'),
  (59, 'cboe', 'Cboe', 'Котировки'),
  (60, 'nasdaq', 'Nasdaq Data Link', 'Котировки'),
  (61, 'nyse', 'NYSE', 'Котировки'),
  (62, 'lse', 'London Stock Exchange', 'Котировки'),
  (63, 'euronext', 'Euronext', 'Котировки'),
  (64, 'deutsche-boerse', 'Deutsche Börse', 'Котировки'),
  (65, 'six-swiss', 'SIX Swiss Exchange', 'Котировки'),
  (66, 'oslo-bors', 'Oslo Børs', 'Котировки'),
  (67, 'nasdaq-omx', 'Nasdaq Nordic', 'Котировки'),
  (68, 'moex', 'MOEX', 'Котировки'),
  (69, 'hkex', 'HKEX', 'Котировки'),
  (70, 'sgx', 'Singapore Exchange', 'Котировки'),
  (71, 'asx', 'ASX', 'Котировки'),
  (72, 'tsx', 'TMX / TSX', 'Котировки'),
  (73, 'b3', 'B3 Brazil', 'Котировки'),
  (74, 'jpx', 'Japan Exchange Group', 'Котировки'),
  (75, 'korea-exchange', 'Korea Exchange', 'Котировки'),
  (76, 'taiwan-exchange', 'Taiwan Stock Exchange', 'Котировки'),
  (77, 'nse-india', 'NSE India', 'Котировки'),
  (78, 'bse-india', 'BSE India', 'Котировки'),
  (79, 'lme', 'London Metal Exchange', 'Котировки'),
  (80, 'shfe', 'Shanghai Futures Exchange', 'Котировки'),
  (81, 'dce', 'Dalian Commodity Exchange', 'Котировки'),
  (82, 'tocom', 'TOCOM', 'Котировки'),
  (83, 'argus', 'Argus Media', 'Котировки'),
  (84, 'platts', 'S&P Global Platts', 'Котировки'),
  (85, 'icis', 'ICIS', 'Котировки'),
  (86, 'opinex', 'Opis / Oil Price Information', 'Котировки'),
  (87, 'yahoo-finance', 'Yahoo Finance', 'Котировки'),
  (88, 'alpha-vantage', 'Alpha Vantage', 'Котировки'),
  (89, 'finnhub', 'Finnhub', 'Котировки'),
  (90, 'polygon-io', 'Polygon.io', 'Котировки'),
  (91, 'tiingo', 'Tiingo', 'Котировки'),
  (92, 'iex-cloud', 'IEX Cloud', 'Котировки'),
  (93, 'twelve-data', 'Twelve Data', 'Котировки'),
  (94, 'stooq', 'Stooq', 'Котировки'),
  (95, 'quandl', 'Nasdaq Quandl legacy', 'Котировки'),
  (96, 'coingecko', 'CoinGecko', 'Котировки'),
  (97, 'coinmarketcap', 'CoinMarketCap', 'Котировки'),
  (98, 'binance-public', 'Binance Public API', 'Котировки'),
  (99, 'kraken-public', 'Kraken Public API', 'Котировки'),
  (100, 'coinbase-exchange', 'Coinbase Exchange API', 'Котировки'),
  (101, 'bitstamp', 'Bitstamp', 'Котировки'),
  (102, 'bybit-public', 'Bybit Public API', 'Котировки'),
  (103, 'okx-public', 'OKX Public API', 'Котировки'),
  (104, 'glassnode', 'Glassnode', 'Котировки'),
  (105, 'defillama', 'DefiLlama', 'Котировки'),
  (106, 'noaa', 'NOAA', 'Экология'),
  (107, 'openweathermap', 'OpenWeatherMap', 'Экология'),
  (108, 'ecmwf', 'ECMWF Open Data', 'Экология'),
  (109, 'met-office', 'Met Office', 'Экология'),
  (110, 'dwd', 'DWD Open Data', 'Экология'),
  (111, 'meteofrance', 'Météo-France', 'Экология'),
  (112, 'nasa-power', 'NASA POWER', 'Экология'),
  (113, 'copernicus-cds', 'Copernicus CDS', 'Экология'),
  (114, 'opensky', 'OpenSky Network', 'Логистика'),
  (115, 'adsb-exchange', 'ADS-B Exchange', 'Логистика'),
  (116, 'flightradar24-api', 'Flightradar24 API', 'Логистика'),
  (117, 'marine-traffic', 'MarineTraffic', 'Логистика'),
  (118, 'ais-hub', 'AISHub', 'Логистика'),
  (119, 'gtfs-realtime', 'GTFS Realtime feeds', 'Логистика'),
  (120, 'transitland', 'Transitland', 'Логистика'),
  (121, 'openstreetmap', 'OpenStreetMap', 'Геоданные'),
  (122, 'overpass', 'Overpass API', 'Геоданные'),
  (123, 'geonames', 'GeoNames', 'Геоданные'),
  (124, 'natural-earth', 'Natural Earth', 'Геоданные'),
  (125, 'open-topo-data', 'OpenTopoData', 'Геоданные'),
  (126, 'usgs', 'USGS', 'Геоданные'),
  (127, 'esa-sentinel', 'ESA Sentinel Hub', 'Геоданные'),
  (128, 'nasa-earthdata', 'NASA Earthdata', 'Геоданные'),
  (129, 'gbif', 'GBIF', 'Наука'),
  (130, 'ncbi', 'NCBI', 'Наука'),
  (131, 'pubmed', 'PubMed / NCBI E-utilities', 'Наука'),
  (132, 'crossref', 'Crossref', 'Наука'),
  (133, 'arxiv', 'arXiv API', 'Наука'),
  (134, 'zenodo', 'Zenodo', 'Наука'),
  (135, 'figshare', 'figshare', 'Наука'),
  (136, 'datacite', 'DataCite', 'Наука'),
  (137, 'orcid', 'ORCID', 'Наука'),
  (138, 'wikidata', 'Wikidata', 'Открытые данные'),
  (139, 'wikipedia-api', 'Wikipedia API', 'Открытые данные'),
  (140, 'dbpedia', 'DBpedia', 'Открытые данные'),
  (141, 'open-library', 'Open Library', 'Открытые данные'),
  (142, 'internet-archive', 'Internet Archive', 'Открытые данные'),
  (143, 'github-archive', 'GH Archive', 'Технологии'),
  (144, 'github-api', 'GitHub REST API', 'Технологии'),
  (145, 'gitlab-api', 'GitLab API', 'Технологии'),
  (146, 'stackexchange', 'Stack Exchange API', 'Технологии'),
  (147, 'hn-firebase', 'Hacker News Firebase', 'Технологии'),
  (148, 'reddit-api', 'Reddit API', 'Технологии'),
  (149, 'mastodon-api', 'Mastodon API', 'Технологии'),
  (150, 'rss-commoncrawl', 'Common Crawl', 'Технологии'),
  (151, 'http-archive', 'HTTP Archive (HAR)', 'Технологии'),
  (152, 'cloudflare-radar', 'Cloudflare Radar', 'Технологии'),
  (153, 'ripe-stat', 'RIPE Stat', 'Технологии'),
  (154, 'peeringdb', 'PeeringDB', 'Технологии'),
  (155, 'iana', 'IANA registries', 'Технологии'),
  (156, 'whois-rdap', 'RDAP / WHOIS', 'Технологии'),
  (157, 'pjm', 'PJM Data Miner', 'Производство'),
  (158, 'caiso', 'CAISO OASIS', 'Производство'),
  (159, 'ercot', 'ERCOT', 'Производство'),
  (160, 'nyiso', 'NYISO', 'Производство'),
  (161, 'miso', 'MISO', 'Производство'),
  (162, 'aemo', 'AEMO', 'Производство'),
  (163, 'national-grid-eso', 'National Grid ESO', 'Производство'),
  (164, 'rte-france', 'RTE France', 'Производство'),
  (165, 'tennet', 'TenneT', 'Производство'),
  (166, '50hertz', '50Hertz', 'Производство'),
  (167, 'amprion', 'Amprion', 'Производство'),
  (168, 'transnetbw', 'TransnetBW', 'Производство'),
  (169, 'gassco', 'Gassco', 'Производство'),
  (170, 'gasunie', 'Gasunie', 'Производство'),
  (171, 'fluxys', 'Fluxys', 'Производство'),
  (172, 'snam', 'Snam', 'Производство'),
  (173, 'enagas', 'Enagás', 'Производство'),
  (174, 'grtgaz', 'GRTgaz', 'Производство'),
  (175, 'iea', 'IEA Data', 'Производство'),
  (176, 'irena', 'IRENA', 'Производство'),
  (177, 'bp-stats', 'Energy Institute / BP Stats', 'Производство'),
  (178, 'ember-climate', 'Ember Climate', 'Производство'),
  (179, 'carbon-monitor', 'Carbon Monitor', 'Производство'),
  (180, 'climate-trace', 'Climate TRACE', 'Производство'),
  (181, 'edgar-jrc', 'EDGAR (JRC)', 'Производство'),
  (182, 'global-carbon-project', 'Global Carbon Project', 'Производство'),
  (183, 'sec-edgar', 'SEC EDGAR', 'Внутренний рынок'),
  (184, 'companies-house', 'Companies House', 'Внутренний рынок'),
  (185, 'opencorporates', 'OpenCorporates', 'Внутренний рынок'),
  (186, 'gleif', 'GLEIF LEI', 'Внутренний рынок'),
  (187, 'fixtr', 'FINTR / trade repository sample', 'Внутренний рынок'),
  (188, 'esma-registers', 'ESMA Registers', 'Внутренний рынок'),
  (189, 'fca-register', 'FCA Register', 'Внутренний рынок'),
  (190, 'cftc-cot', 'CFTC Commitments of Traders', 'Внутренний рынок'),
  (191, 'finra-otc', 'FINRA OTC', 'Внутренний рынок'),
  (192, 'msrb-emma', 'MSRB EMMA', 'Внутренний рынок'),
  (193, 'treasury-gov', 'US Treasury Fiscal Data', 'Внутренний рынок'),
  (194, 'ofd-io', 'Open Fiscal Data', 'Внутренний рынок'),
  (195, 'opensanctions', 'OpenSanctions', 'Внутренний рынок'),
  (196, 'opensky-flights', 'OpenSky flights dump', 'Логистика'),
  (197, 'eurocontrol', 'EUROCONTROL NM', 'Логистика'),
  (198, 'icao', 'ICAO data+', 'Логистика'),
  (199, 'iata', 'IATA', 'Логистика'),
  (200, 'uk-dft', 'UK DfT', 'Логистика'),
  (201, 'sncf-open', 'SNCF Open Data', 'Логистика'),
  (202, 'db-opendata', 'Deutsche Bahn Open Data', 'Логистика'),
  (203, 'transport-api-uk', 'TransportAPI UK', 'Логистика'),
  (204, 'citybikes', 'CityBikes', 'Логистика'),
  (205, 'gbfs', 'GBFS feeds', 'Логистика'),
  (206, 'openchargemap', 'Open Charge Map', 'Производство'),
  (207, 'nrel-api', 'NREL API', 'Производство'),
  (208, 'pvoutput', 'PVOutput', 'Производство'),
  (209, 'renewables-ninja', 'Renewables.ninja', 'Производство'),
  (210, 'electricity-maps', 'Electricity Maps', 'Производство'),
  (211, 'watttime', 'WattTime', 'Производство'),
  (212, 'carbon-intensity-uk', 'UK Carbon Intensity', 'Производство'),
  (213, 'co2-signal', 'CO2 Signal', 'Производство'),
  (214, 'openaq', 'OpenAQ', 'Экология'),
  (215, 'airnow', 'AirNow', 'Экология'),
  (216, 'eea', 'European Environment Agency', 'Экология'),
  (217, 'epa', 'US EPA', 'Экология'),
  (218, 'global-forest-watch', 'Global Forest Watch', 'Экология'),
  (219, 'global-fishing-watch', 'Global Fishing Watch', 'Экология'),
  (220, 'protected-planet', 'Protected Planet', 'Экология'),
  (221, 'ocean-acidification', 'NOAA Ocean Acidification', 'Экология'),
  (222, 'argo-floats', 'Argo floats', 'Экология'),
  (223, 'copernicus-marine', 'Copernicus Marine', 'Экология'),
  (224, 'gebco', 'GEBCO', 'Геоданные'),
  (225, 'natural-earth-raster', 'Natural Earth rasters', 'Геоданные'),
  (226, 'opentopography', 'OpenTopography', 'Геоданные'),
  (227, 'srtm', 'SRTM', 'Геоданные'),
  (228, 'landsat', 'Landsat', 'Геоданные'),
  (229, 'modis', 'MODIS', 'Геоданные'),
  (230, 'viirs', 'VIIRS', 'Геоданные'),
  (231, 'google-earth-engine', 'Google Earth Engine catalogs', 'Геоданные'),
  (232, 'microsoft-planetary', 'Microsoft Planetary Computer', 'Геоданные'),
  (233, 'aws-open-data', 'AWS Open Data Registry', 'Открытые данные'),
  (234, 'azure-opendata', 'Azure Open Datasets', 'Открытые данные'),
  (235, 'gcp-public-data', 'GCP Public Datasets', 'Открытые данные'),
  (236, 'kaggle', 'Kaggle Datasets', 'Открытые данные'),
  (237, 'huggingface-datasets', 'Hugging Face Datasets', 'Открытые данные'),
  (238, 'uciml', 'UCI ML Repository', 'Открытые данные'),
  (239, 'dataverse', 'Harvard Dataverse', 'Наука'),
  (240, 'dryad', 'Dryad', 'Наука'),
  (241, 'figshare-oai', 'figshare OAI-PMH', 'Наука'),
  (242, 'europe-pmc', 'Europe PMC', 'Наука'),
  (243, 'uniprot', 'UniProt', 'Наука'),
  (244, 'pdb', 'RCSB PDB', 'Наука'),
  (245, 'chembl', 'ChEMBL', 'Наука'),
  (246, 'pubchem', 'PubChem', 'Наука'),
  (247, 'openfda', 'openFDA', 'Наука'),
  (248, 'clinicaltrials', 'ClinicalTrials.gov', 'Наука'),
  (249, 'rxnorm', 'RxNorm', 'Наука'),
  (250, 'snomed-browser', 'SNOMED CT browser data', 'Наука'),
  (251, 'loinc', 'LOINC', 'Наука'),
  (252, 'hl7-fhir-samples', 'HL7 FHIR sample servers', 'Наука'),
  (253, 'gdelt', 'GDELT', 'СМИ'),
  (254, 'mediacloud', 'Media Cloud', 'СМИ'),
  (255, 'newsapi', 'NewsAPI', 'СМИ'),
  (256, 'guardian-api', 'The Guardian Open Platform', 'СМИ'),
  (257, 'nytimes-api', 'NYTimes API', 'СМИ'),
  (258, 'bbc-rss', 'BBC RSS / feeds', 'СМИ'),
  (259, 'reuters-rss', 'Reuters RSS', 'СМИ'),
  (260, 'ap-news-rss', 'AP News RSS', 'СМИ')
),
picked AS (
  SELECT
    c.ord AS i,
    c.slug AS key,
    c.title,
    c.kind,
    (
      substr(md5('universe_bulk:ds:' || c.slug), 1, 8) || '-' ||
      substr(md5('universe_bulk:ds:' || c.slug), 9, 4) || '-' ||
      '4' || substr(md5('universe_bulk:ds:' || c.slug), 14, 3) || '-' ||
      'a' || substr(md5('universe_bulk:ds:' || c.slug), 18, 3) || '-' ||
      substr(md5('universe_bulk:ds:' || c.slug), 21, 12)
    )::uuid AS ds_id,
    (
      substr(md5('universe_bulk:es:' || c.slug), 1, 8) || '-' ||
      substr(md5('universe_bulk:es:' || c.slug), 9, 4) || '-' ||
      '4' || substr(md5('universe_bulk:es:' || c.slug), 14, 3) || '-' ||
      'a' || substr(md5('universe_bulk:es:' || c.slug), 18, 3) || '-' ||
      substr(md5('universe_bulk:es:' || c.slug), 21, 12)
    )::uuid AS es_id,
    (
      substr(md5('universe_bulk:proc:' || c.slug), 1, 8) || '-' ||
      substr(md5('universe_bulk:proc:' || c.slug), 9, 4) || '-' ||
      '4' || substr(md5('universe_bulk:proc:' || c.slug), 14, 3) || '-' ||
      'a' || substr(md5('universe_bulk:proc:' || c.slug), 18, 3) || '-' ||
      substr(md5('universe_bulk:proc:' || c.slug), 21, 12)
    )::uuid AS proc_id
  FROM catalog c
  WHERE c.ord <= least((SELECT n FROM params), (SELECT max(ord) FROM catalog))
),
ins_ds AS (
  INSERT INTO sol_dwh_portal.portal_assets (
    id, asset_type, qualified_name, name, description,
    source_provider, native_id, identity_key,
    first_seen_at, last_seen_at, deleted_at, attributes
  )
  SELECT
    ds_id,
    'DATA_SOURCE',
    'datasource:' || key,
    title,
    'Public/demo DATA_SOURCE · ' || kind,
    (SELECT provider FROM params),
    key,
    'datasource:' || key,
    (SELECT ts FROM params),
    (SELECT ts FROM params),
    NULL,
    jsonb_build_object('seed', 'universe_bulk', 'bulk_index', i, 'kind', kind)
  FROM picked
  RETURNING id
),
ins_es AS (
  INSERT INTO sol_dwh_portal.portal_assets (
    id, asset_type, qualified_name, name, description,
    source_provider, native_id, identity_key,
    first_seen_at, last_seen_at, deleted_at, attributes
  )
  SELECT
    es_id,
    'EXTRACTION_SOURCE',
    'extraction:' || key,
    replace(key, '-', '_') || '_feed',
    'Public feed extractor for ' || title,
    (SELECT provider FROM params),
    key,
    'extraction:' || key,
    (SELECT ts FROM params),
    (SELECT ts FROM params),
    NULL,
    jsonb_build_object(
      'seed', 'universe_bulk',
      'bulk_index', i,
      'kind', kind,
      'is_active', true,
      'extract_source_type_id', 1
    )
  FROM picked
  RETURNING id
),
ins_proc AS (
  INSERT INTO sol_dwh_portal.portal_assets (
    id, asset_type, qualified_name, name, description,
    source_provider, native_id, identity_key,
    first_seen_at, last_seen_at, deleted_at, attributes
  )
  SELECT
    proc_id,
    'PROCESS',
    'process:' || key || ':loader',
    'load_' || replace(key, '-', '_'),
    'Demo loader for ' || title,
    (SELECT provider FROM params),
    key || ':loader',
    'process:' || key || ':loader',
    (SELECT ts FROM params),
    (SELECT ts FROM params),
    NULL,
    jsonb_build_object(
      'seed', 'universe_bulk',
      'bulk_index', i,
      'kind', kind,
      'handler_type', 'Python',
      'metadata_status', 'OK',
      'lineage_status', 'RESOLVED',
      'extraction_source_id', key
    )
  FROM picked
  RETURNING id
),
ins_rel AS (
  INSERT INTO sol_dwh_portal.portal_relationships (
    from_asset_id, to_asset_id, relationship_type, source_provider, native_id, attributes
  )
  SELECT ds_id, es_id, 'EXTRACTS_TO', (SELECT provider FROM params), NULL,
         jsonb_build_object('seed', 'universe_bulk')
  FROM picked
  UNION ALL
  SELECT es_id, proc_id, 'EXTRACTS_TO', (SELECT provider FROM params), NULL,
         jsonb_build_object('seed', 'universe_bulk')
  FROM picked
  RETURNING id
)
SELECT
  (SELECT count(*) FROM ins_ds)   AS data_sources,
  (SELECT count(*) FROM ins_es)   AS extraction_sources,
  (SELECT count(*) FROM ins_proc) AS processes,
  (SELECT count(*) FROM ins_rel)  AS relationships;

COMMIT;

SELECT asset_type, count(*) AS n
FROM sol_dwh_portal.portal_assets
WHERE deleted_at IS NULL
  AND asset_type IN ('DATA_SOURCE', 'EXTRACTION_SOURCE', 'PROCESS')
GROUP BY asset_type
ORDER BY asset_type;

SELECT name
FROM sol_dwh_portal.portal_assets
WHERE attributes->>'seed' = 'universe_bulk'
  AND asset_type = 'DATA_SOURCE'
ORDER BY name
LIMIT 12;
