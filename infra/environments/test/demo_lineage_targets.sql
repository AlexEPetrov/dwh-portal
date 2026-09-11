-- Demo lineage targets for portal_lineage_fixtures get_metadata() writes_to.
-- Safe to re-run. Does not drop existing ICE/inbox production-like tables.
-- Pair with: infra/environments/test/samples.sql

BEGIN;

CREATE SCHEMA IF NOT EXISTS src_cme;
CREATE SCHEMA IF NOT EXISTS src_eex;
CREATE SCHEMA IF NOT EXISTS src_argus;

COMMENT ON SCHEMA src_cme IS 'Demo CME/NYMEX settlement landing schema';
COMMENT ON SCHEMA src_eex IS 'Demo EEX spot landing schema';
COMMENT ON SCHEMA src_argus IS 'Demo Argus assessments landing schema';

-- ---------------------------------------------------------------------------
-- ICE views over existing tables
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW inbox.v_ice_options_daily_market_reports_latest AS
SELECT DISTINCT ON (product_code, contract_month, strike_price, option_type)
  *
FROM inbox.inbox_ice_options_daily_market_reports
ORDER BY product_code, contract_month, strike_price, option_type, report_date DESC;

COMMENT ON VIEW inbox.v_ice_options_daily_market_reports_latest IS
  'Latest ICE Brent options settlement row per contract/strike';

CREATE OR REPLACE VIEW src_ice.v_ice_futures_daily_market_reports_latest AS
SELECT DISTINCT ON (product_code, contract_month)
  *
FROM src_ice.ice_futures_daily_market_reports
ORDER BY product_code, contract_month, report_date DESC;

COMMENT ON VIEW src_ice.v_ice_futures_daily_market_reports_latest IS
  'Latest ICE futures DMR row per product/contract month';

CREATE OR REPLACE VIEW src_ice.v_ice_cot_daily_reports_latest AS
SELECT DISTINCT ON (venue_product_code)
  *
FROM src_ice.ice_cot_daily_reports
ORDER BY venue_product_code, date_of_which_the_weekly_report_refers DESC NULLS LAST;

COMMENT ON VIEW src_ice.v_ice_cot_daily_reports_latest IS
  'Latest ICE COT report row per venue product code';

-- ---------------------------------------------------------------------------
-- CME / NYMEX
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS src_cme.cme_cl_settlements (
  rid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  report_date date NOT NULL,
  product_code varchar NOT NULL,
  contract_month date NOT NULL,
  settlement_price numeric,
  volume_total integer,
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE src_cme.cme_cl_settlements IS 'CME CL (WTI) futures settlements (demo)';
COMMENT ON COLUMN src_cme.cme_cl_settlements.report_date IS 'Settlement trade date';
COMMENT ON COLUMN src_cme.cme_cl_settlements.product_code IS 'CME product code (e.g. CL)';
COMMENT ON COLUMN src_cme.cme_cl_settlements.contract_month IS 'Futures contract month';
COMMENT ON COLUMN src_cme.cme_cl_settlements.settlement_price IS 'Official settlement price';

CREATE OR REPLACE VIEW src_cme.v_cme_cl_settlements_latest AS
SELECT DISTINCT ON (product_code, contract_month) *
FROM src_cme.cme_cl_settlements
ORDER BY product_code, contract_month, report_date DESC;
COMMENT ON VIEW src_cme.v_cme_cl_settlements_latest IS 'Latest CME CL settlement per contract';

CREATE TABLE IF NOT EXISTS src_cme.cme_ng_settlements (
  rid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  report_date date NOT NULL,
  product_code varchar NOT NULL,
  contract_month date NOT NULL,
  settlement_price numeric,
  volume_total integer,
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE src_cme.cme_ng_settlements IS 'CME NG (Henry Hub) futures settlements (demo)';

CREATE OR REPLACE VIEW src_cme.v_cme_ng_settlements_latest AS
SELECT DISTINCT ON (product_code, contract_month) *
FROM src_cme.cme_ng_settlements
ORDER BY product_code, contract_month, report_date DESC;
COMMENT ON VIEW src_cme.v_cme_ng_settlements_latest IS 'Latest CME NG settlement per contract';

CREATE TABLE IF NOT EXISTS src_cme.nymex_rbob_settlements (
  rid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  report_date date NOT NULL,
  product_code varchar NOT NULL,
  contract_month date NOT NULL,
  settlement_price numeric,
  volume_total integer,
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE src_cme.nymex_rbob_settlements IS 'NYMEX RBOB gasoline futures settlements (demo)';

CREATE OR REPLACE VIEW src_cme.v_nymex_rbob_settlements_latest AS
SELECT DISTINCT ON (product_code, contract_month) *
FROM src_cme.nymex_rbob_settlements
ORDER BY product_code, contract_month, report_date DESC;
COMMENT ON VIEW src_cme.v_nymex_rbob_settlements_latest IS 'Latest NYMEX RBOB settlement per contract';

-- ---------------------------------------------------------------------------
-- EEX
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS src_eex.eex_power_spot (
  rid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  delivery_date date NOT NULL,
  market_area varchar NOT NULL,
  price_eur_mwh numeric,
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE src_eex.eex_power_spot IS 'EEX day-ahead power spot prices (demo)';
COMMENT ON COLUMN src_eex.eex_power_spot.market_area IS 'Bidding zone / market area code';

CREATE OR REPLACE VIEW src_eex.v_eex_power_spot_latest AS
SELECT DISTINCT ON (market_area) *
FROM src_eex.eex_power_spot
ORDER BY market_area, delivery_date DESC;
COMMENT ON VIEW src_eex.v_eex_power_spot_latest IS 'Latest EEX power spot per market area';

CREATE TABLE IF NOT EXISTS src_eex.eex_gas_spot (
  rid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  delivery_date date NOT NULL,
  hub varchar NOT NULL,
  price_eur_mwh numeric,
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE src_eex.eex_gas_spot IS 'EEX natural gas spot indices (demo)';
COMMENT ON COLUMN src_eex.eex_gas_spot.hub IS 'Gas hub code (e.g. THE, TTF)';

CREATE OR REPLACE VIEW src_eex.v_eex_gas_spot_latest AS
SELECT DISTINCT ON (hub) *
FROM src_eex.eex_gas_spot
ORDER BY hub, delivery_date DESC;
COMMENT ON VIEW src_eex.v_eex_gas_spot_latest IS 'Latest EEX gas spot per hub';

-- ---------------------------------------------------------------------------
-- Argus
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS src_argus.argus_crude_assessments (
  rid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assessment_date date NOT NULL,
  grade varchar NOT NULL,
  price_usd_bbl numeric,
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE src_argus.argus_crude_assessments IS 'Argus crude price assessments (demo)';

CREATE OR REPLACE VIEW src_argus.v_argus_crude_assessments_latest AS
SELECT DISTINCT ON (grade) *
FROM src_argus.argus_crude_assessments
ORDER BY grade, assessment_date DESC;
COMMENT ON VIEW src_argus.v_argus_crude_assessments_latest IS 'Latest Argus crude assessment per grade';

CREATE TABLE IF NOT EXISTS src_argus.argus_products_assessments (
  rid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assessment_date date NOT NULL,
  product_name varchar NOT NULL,
  price_usd_mt numeric,
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE src_argus.argus_products_assessments IS 'Argus refined products assessments (demo)';

CREATE OR REPLACE VIEW src_argus.v_argus_products_assessments_latest AS
SELECT DISTINCT ON (product_name) *
FROM src_argus.argus_products_assessments
ORDER BY product_name, assessment_date DESC;
COMMENT ON VIEW src_argus.v_argus_products_assessments_latest IS 'Latest Argus products assessment per product';

CREATE TABLE IF NOT EXISTS src_argus.argus_products_assessments_curated (
  rid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assessment_date date NOT NULL,
  product_code varchar NOT NULL,
  price_usd_mt numeric,
  source_rid uuid,
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE src_argus.argus_products_assessments_curated IS
  'Curated/normalized Argus products (second process in dual-handler demo)';

CREATE OR REPLACE VIEW src_argus.v_argus_products_assessments_curated AS
SELECT DISTINCT ON (product_code) *
FROM src_argus.argus_products_assessments_curated
ORDER BY product_code, assessment_date DESC;
COMMENT ON VIEW src_argus.v_argus_products_assessments_curated IS
  'Latest curated Argus products row per product_code';

-- ---------------------------------------------------------------------------
-- Cross-source demo: one VIEW derived from tables of different sources
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS src_market;
COMMENT ON SCHEMA src_market IS 'Demo cross-source curated market views';

CREATE OR REPLACE VIEW src_market.v_cross_source_prices AS
SELECT
  'eex'::text AS source_system,
  delivery_date AS price_date,
  market_area AS symbol,
  price_eur_mwh AS price
FROM src_eex.eex_power_spot
UNION ALL
SELECT
  'cme'::text AS source_system,
  report_date AS price_date,
  product_code AS symbol,
  settlement_price AS price
FROM src_cme.cme_cl_settlements;

COMMENT ON VIEW src_market.v_cross_source_prices IS
  'Demo unified prices from EEX power + CME CL (multi-table DERIVED_FROM)';

COMMIT;
