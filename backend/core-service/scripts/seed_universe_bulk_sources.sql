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
-- slug, display name, short kind (for extraction/process labels)
catalog (ord, slug, title, kind) AS (
  VALUES
  (1,  'fred', 'FRED (St. Louis Fed)', 'macro'),
  (2,  'ecb-sdw', 'ECB Statistical Data Warehouse', 'macro'),
  (3,  'bis-stats', 'BIS Statistics', 'macro'),
  (4,  'imf-data', 'IMF Data', 'macro'),
  (5,  'world-bank', 'World Bank Open Data', 'macro'),
  (6,  'oecd-data', 'OECD Data', 'macro'),
  (7,  'eurostat', 'Eurostat', 'macro'),
  (8,  'ons-uk', 'ONS UK', 'macro'),
  (9,  'insee', 'INSEE', 'macro'),
  (10, 'destatis', 'Destatis', 'macro'),
  (11, 'istat', 'Istat', 'macro'),
  (12, 'cbr', 'Bank of Russia', 'macro'),
  (13, 'boj', 'Bank of Japan', 'macro'),
  (14, 'boe', 'Bank of England', 'macro'),
  (15, 'snb', 'Swiss National Bank', 'macro'),
  (16, 'riksbank', 'Riksbank', 'macro'),
  (17, 'nbp', 'Narodowy Bank Polski', 'macro'),
  (18, 'cnb', 'Czech National Bank', 'macro'),
  (19, 'mnb', 'Magyar Nemzeti Bank', 'macro'),
  (20, 'norges-bank', 'Norges Bank', 'macro'),
  (21, 'rba', 'Reserve Bank of Australia', 'macro'),
  (22, 'rbnz', 'Reserve Bank of New Zealand', 'macro'),
  (23, 'bank-canada', 'Bank of Canada', 'macro'),
  (24, 'bls', 'US BLS', 'macro'),
  (25, 'bea', 'US BEA', 'macro'),
  (26, 'census-bureau', 'US Census Bureau', 'macro'),
  (27, 'data-gov', 'Data.gov', 'opendata'),
  (28, 'data-gov-uk', 'data.gov.uk', 'opendata'),
  (29, 'data-gouv-fr', 'data.gouv.fr', 'opendata'),
  (30, 'govdata-de', 'GovData.de', 'opendata'),
  (31, 'datos-gob-es', 'datos.gob.es', 'opendata'),
  (32, 'dati-gov-it', 'dati.gov.it', 'opendata'),
  (33, 'opendata-swiss', 'opendata.swiss', 'opendata'),
  (34, 'data-gov-sg', 'data.gov.sg', 'opendata'),
  (35, 'data-gov-au', 'data.gov.au', 'opendata'),
  (36, 'data-canada', 'Open Government Canada', 'opendata'),
  (37, 'eu-opendata', 'data.europa.eu', 'opendata'),
  (38, 'who-gho', 'WHO Global Health Observatory', 'opendata'),
  (39, 'unicef-data', 'UNICEF Data', 'opendata'),
  (40, 'un-comtrade', 'UN Comtrade', 'trade'),
  (41, 'wto-stats', 'WTO Stats', 'trade'),
  (42, 'faostat', 'FAOSTAT', 'opendata'),
  (43, 'iloistat', 'ILOSTAT', 'opendata'),
  (44, 'our-world-in-data', 'Our World in Data', 'opendata'),
  (45, 'gapminder', 'Gapminder', 'opendata'),
  (46, 'eia', 'US EIA', 'energy'),
  (47, 'entsoe', 'ENTSO-E Transparency', 'energy'),
  (48, 'acer', 'ACER REMIT', 'energy'),
  (49, 'gie-agsi', 'GIE AGSI+', 'energy'),
  (50, 'gie-alsi', 'GIE ALSI', 'energy'),
  (51, 'entsog', 'ENTSOG TP', 'energy'),
  (52, 'nord-pool', 'Nord Pool', 'energy'),
  (53, 'epex-spot', 'EPEX SPOT', 'energy'),
  (54, 'eex', 'EEX', 'energy'),
  (55, 'ice', 'ICE', 'market'),
  (56, 'cme', 'CME Group', 'market'),
  (57, 'nymex', 'NYMEX', 'market'),
  (58, 'comex', 'COMEX', 'market'),
  (59, 'cboe', 'Cboe', 'market'),
  (60, 'nasdaq', 'Nasdaq Data Link', 'market'),
  (61, 'nyse', 'NYSE', 'market'),
  (62, 'lse', 'London Stock Exchange', 'market'),
  (63, 'euronext', 'Euronext', 'market'),
  (64, 'deutsche-boerse', 'Deutsche Börse', 'market'),
  (65, 'six-swiss', 'SIX Swiss Exchange', 'market'),
  (66, 'oslo-bors', 'Oslo Børs', 'market'),
  (67, 'nasdaq-omx', 'Nasdaq Nordic', 'market'),
  (68, 'moex', 'MOEX', 'market'),
  (69, 'hkex', 'HKEX', 'market'),
  (70, 'sgx', 'Singapore Exchange', 'market'),
  (71, 'asx', 'ASX', 'market'),
  (72, 'tsx', 'TMX / TSX', 'market'),
  (73, 'b3', 'B3 Brazil', 'market'),
  (74, 'jpx', 'Japan Exchange Group', 'market'),
  (75, 'korea-exchange', 'Korea Exchange', 'market'),
  (76, 'taiwan-exchange', 'Taiwan Stock Exchange', 'market'),
  (77, 'nse-india', 'NSE India', 'market'),
  (78, 'bse-india', 'BSE India', 'market'),
  (79, 'lme', 'London Metal Exchange', 'market'),
  (80, 'shfe', 'Shanghai Futures Exchange', 'market'),
  (81, 'dce', 'Dalian Commodity Exchange', 'market'),
  (82, 'tocom', 'TOCOM', 'market'),
  (83, 'argus', 'Argus Media', 'price'),
  (84, 'platts', 'S&P Global Platts', 'price'),
  (85, 'icis', 'ICIS', 'price'),
  (86, 'opinex', 'Opis / Oil Price Information', 'price'),
  (87, 'yahoo-finance', 'Yahoo Finance', 'market'),
  (88, 'alpha-vantage', 'Alpha Vantage', 'market'),
  (89, 'finnhub', 'Finnhub', 'market'),
  (90, 'polygon-io', 'Polygon.io', 'market'),
  (91, 'tiingo', 'Tiingo', 'market'),
  (92, 'iex-cloud', 'IEX Cloud', 'market'),
  (93, 'twelve-data', 'Twelve Data', 'market'),
  (94, 'stooq', 'Stooq', 'market'),
  (95, 'quandl', 'Nasdaq Quandl legacy', 'market'),
  (96, 'coingecko', 'CoinGecko', 'crypto'),
  (97, 'coinmarketcap', 'CoinMarketCap', 'crypto'),
  (98, 'binance-public', 'Binance Public API', 'crypto'),
  (99, 'kraken-public', 'Kraken Public API', 'crypto'),
  (100, 'coinbase-exchange', 'Coinbase Exchange API', 'crypto'),
  (101, 'bitstamp', 'Bitstamp', 'crypto'),
  (102, 'bybit-public', 'Bybit Public API', 'crypto'),
  (103, 'okx-public', 'OKX Public API', 'crypto'),
  (104, 'glassnode', 'Glassnode', 'crypto'),
  (105, 'defillama', 'DefiLlama', 'crypto'),
  (106, 'noaa', 'NOAA', 'weather'),
  (107, 'openweathermap', 'OpenWeatherMap', 'weather'),
  (108, 'ecmwf', 'ECMWF Open Data', 'weather'),
  (109, 'met-office', 'Met Office', 'weather'),
  (110, 'dwd', 'DWD Open Data', 'weather'),
  (111, 'meteofrance', 'Météo-France', 'weather'),
  (112, 'nasa-power', 'NASA POWER', 'weather'),
  (113, 'copernicus-cds', 'Copernicus CDS', 'weather'),
  (114, 'opensky', 'OpenSky Network', 'transport'),
  (115, 'adsb-exchange', 'ADS-B Exchange', 'transport'),
  (116, 'flightradar24-api', 'Flightradar24 API', 'transport'),
  (117, 'marine-traffic', 'MarineTraffic', 'transport'),
  (118, 'ais-hub', 'AISHub', 'transport'),
  (119, 'gtfs-realtime', 'GTFS Realtime feeds', 'transport'),
  (120, 'transitland', 'Transitland', 'transport'),
  (121, 'openstreetmap', 'OpenStreetMap', 'geo'),
  (122, 'overpass', 'Overpass API', 'geo'),
  (123, 'geonames', 'GeoNames', 'geo'),
  (124, 'natural-earth', 'Natural Earth', 'geo'),
  (125, 'open-topo-data', 'OpenTopoData', 'geo'),
  (126, 'usgs', 'USGS', 'geo'),
  (127, 'esa-sentinel', 'ESA Sentinel Hub', 'geo'),
  (128, 'nasa-earthdata', 'NASA Earthdata', 'geo'),
  (129, 'gbif', 'GBIF', 'science'),
  (130, 'ncbi', 'NCBI', 'science'),
  (131, 'pubmed', 'PubMed / NCBI E-utilities', 'science'),
  (132, 'crossref', 'Crossref', 'science'),
  (133, 'arxiv', 'arXiv API', 'science'),
  (134, 'zenodo', 'Zenodo', 'science'),
  (135, 'figshare', 'figshare', 'science'),
  (136, 'datacite', 'DataCite', 'science'),
  (137, 'orcid', 'ORCID', 'science'),
  (138, 'wikidata', 'Wikidata', 'opendata'),
  (139, 'wikipedia-api', 'Wikipedia API', 'opendata'),
  (140, 'dbpedia', 'DBpedia', 'opendata'),
  (141, 'open-library', 'Open Library', 'opendata'),
  (142, 'internet-archive', 'Internet Archive', 'opendata'),
  (143, 'github-archive', 'GH Archive', 'tech'),
  (144, 'github-api', 'GitHub REST API', 'tech'),
  (145, 'gitlab-api', 'GitLab API', 'tech'),
  (146, 'stackexchange', 'Stack Exchange API', 'tech'),
  (147, 'hn-firebase', 'Hacker News Firebase', 'tech'),
  (148, 'reddit-api', 'Reddit API', 'tech'),
  (149, 'mastodon-api', 'Mastodon API', 'tech'),
  (150, 'rss-commoncrawl', 'Common Crawl', 'tech'),
  (151, 'http-archive', 'HTTP Archive (HAR)', 'tech'),
  (152, 'cloudflare-radar', 'Cloudflare Radar', 'tech'),
  (153, 'ripe-stat', 'RIPE Stat', 'tech'),
  (154, 'peeringdb', 'PeeringDB', 'tech'),
  (155, 'iana', 'IANA registries', 'tech'),
  (156, 'whois-rdap', 'RDAP / WHOIS', 'tech'),
  (157, 'pjm', 'PJM Data Miner', 'energy'),
  (158, 'caiso', 'CAISO OASIS', 'energy'),
  (159, 'ercot', 'ERCOT', 'energy'),
  (160, 'nyiso', 'NYISO', 'energy'),
  (161, 'miso', 'MISO', 'energy'),
  (162, 'aemo', 'AEMO', 'energy'),
  (163, 'national-grid-eso', 'National Grid ESO', 'energy'),
  (164, 'rte-france', 'RTE France', 'energy'),
  (165, 'tennet', 'TenneT', 'energy'),
  (166, '50hertz', '50Hertz', 'energy'),
  (167, 'amprion', 'Amprion', 'energy'),
  (168, 'transnetbw', 'TransnetBW', 'energy'),
  (169, 'gassco', 'Gassco', 'energy'),
  (170, 'gasunie', 'Gasunie', 'energy'),
  (171, 'fluxys', 'Fluxys', 'energy'),
  (172, 'snam', 'Snam', 'energy'),
  (173, 'enagas', 'Enagás', 'energy'),
  (174, 'grtgaz', 'GRTgaz', 'energy'),
  (175, 'iea', 'IEA Data', 'energy'),
  (176, 'irena', 'IRENA', 'energy'),
  (177, 'bp-stats', 'Energy Institute / BP Stats', 'energy'),
  (178, 'ember-climate', 'Ember Climate', 'energy'),
  (179, 'carbon-monitor', 'Carbon Monitor', 'energy'),
  (180, 'climate-trace', 'Climate TRACE', 'energy'),
  (181, 'edgar-jrc', 'EDGAR (JRC)', 'energy'),
  (182, 'global-carbon-project', 'Global Carbon Project', 'energy'),
  (183, 'sec-edgar', 'SEC EDGAR', 'finance'),
  (184, 'companies-house', 'Companies House', 'finance'),
  (185, 'opencorporates', 'OpenCorporates', 'finance'),
  (186, 'gleif', 'GLEIF LEI', 'finance'),
  (187, 'fixtr', 'FINTR / trade repository sample', 'finance'),
  (188, 'esma-registers', 'ESMA Registers', 'finance'),
  (189, 'fca-register', 'FCA Register', 'finance'),
  (190, 'cftc-cot', 'CFTC Commitments of Traders', 'finance'),
  (191, 'finra-otc', 'FINRA OTC', 'finance'),
  (192, 'msrb-emma', 'MSRB EMMA', 'finance'),
  (193, 'treasury-gov', 'US Treasury Fiscal Data', 'finance'),
  (194, 'ofd-io', 'Open Fiscal Data', 'finance'),
  (195, 'opensanctions', 'OpenSanctions', 'finance'),
  (196, 'opensky-flights', 'OpenSky flights dump', 'transport'),
  (197, 'eurocontrol', 'EUROCONTROL NM', 'transport'),
  (198, 'icao', 'ICAO data+', 'transport'),
  (199, 'iata', 'IATA', 'transport'),
  (200, 'uk-dft', 'UK DfT', 'transport'),
  (201, 'sncf-open', 'SNCF Open Data', 'transport'),
  (202, 'db-opendata', 'Deutsche Bahn Open Data', 'transport'),
  (203, 'transport-api-uk', 'TransportAPI UK', 'transport'),
  (204, 'citybikes', 'CityBikes', 'transport'),
  (205, 'gbfs', 'GBFS feeds', 'transport'),
  (206, 'openchargemap', 'Open Charge Map', 'energy'),
  (207, 'nrel-api', 'NREL API', 'energy'),
  (208, 'pvoutput', 'PVOutput', 'energy'),
  (209, 'renewables-ninja', 'Renewables.ninja', 'energy'),
  (210, 'electricity-maps', 'Electricity Maps', 'energy'),
  (211, 'watttime', 'WattTime', 'energy'),
  (212, 'carbon-intensity-uk', 'UK Carbon Intensity', 'energy'),
  (213, 'co2-signal', 'CO2 Signal', 'energy'),
  (214, 'openaq', 'OpenAQ', 'environment'),
  (215, 'airnow', 'AirNow', 'environment'),
  (216, 'eea', 'European Environment Agency', 'environment'),
  (217, 'epa', 'US EPA', 'environment'),
  (218, 'global-forest-watch', 'Global Forest Watch', 'environment'),
  (219, 'global-fishing-watch', 'Global Fishing Watch', 'environment'),
  (220, 'protected-planet', 'Protected Planet', 'environment'),
  (221, 'ocean-acidification', 'NOAA Ocean Acidification', 'environment'),
  (222, 'argo-floats', 'Argo floats', 'environment'),
  (223, 'copernicus-marine', 'Copernicus Marine', 'environment'),
  (224, 'gebco', 'GEBCO', 'geo'),
  (225, 'natural-earth-raster', 'Natural Earth rasters', 'geo'),
  (226, 'opentopography', 'OpenTopography', 'geo'),
  (227, 'srtm', 'SRTM', 'geo'),
  (228, 'landsat', 'Landsat', 'geo'),
  (229, 'modis', 'MODIS', 'geo'),
  (230, 'viirs', 'VIIRS', 'geo'),
  (231, 'google-earth-engine', 'Google Earth Engine catalogs', 'geo'),
  (232, 'microsoft-planetary', 'Microsoft Planetary Computer', 'geo'),
  (233, 'aws-open-data', 'AWS Open Data Registry', 'opendata'),
  (234, 'azure-opendata', 'Azure Open Datasets', 'opendata'),
  (235, 'gcp-public-data', 'GCP Public Datasets', 'opendata'),
  (236, 'kaggle', 'Kaggle Datasets', 'opendata'),
  (237, 'huggingface-datasets', 'Hugging Face Datasets', 'opendata'),
  (238, 'uciml', 'UCI ML Repository', 'opendata'),
  (239, 'dataverse', 'Harvard Dataverse', 'science'),
  (240, 'dryad', 'Dryad', 'science'),
  (241, 'figshare-oai', 'figshare OAI-PMH', 'science'),
  (242, 'europe-pmc', 'Europe PMC', 'science'),
  (243, 'uniprot', 'UniProt', 'science'),
  (244, 'pdb', 'RCSB PDB', 'science'),
  (245, 'chembl', 'ChEMBL', 'science'),
  (246, 'pubchem', 'PubChem', 'science'),
  (247, 'openfda', 'openFDA', 'science'),
  (248, 'clinicaltrials', 'ClinicalTrials.gov', 'science'),
  (249, 'rxnorm', 'RxNorm', 'science'),
  (250, 'snomed-browser', 'SNOMED CT browser data', 'science'),
  (251, 'loinc', 'LOINC', 'science'),
  (252, 'hl7-fhir-samples', 'HL7 FHIR sample servers', 'science'),
  (253, 'gdelt', 'GDELT', 'news'),
  (254, 'mediacloud', 'Media Cloud', 'news'),
  (255, 'newsapi', 'NewsAPI', 'news'),
  (256, 'guardian-api', 'The Guardian Open Platform', 'news'),
  (257, 'nytimes-api', 'NYTimes API', 'news'),
  (258, 'bbc-rss', 'BBC RSS / feeds', 'news'),
  (259, 'reuters-rss', 'Reuters RSS', 'news'),
  (260, 'ap-news-rss', 'AP News RSS', 'news')
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
