-- Portal lineage test seed: ~10 extraction sources
-- Live columns: id, name, descr, extract_options, storage_options,
--               load_options, load_schedule_id, data_source_id, parent_id
-- writes_to comes from get_metadata() in portal_lineage_fixtures/*.
-- Create physical targets with: demo_lineage_targets.sql

BEGIN;

-- ---------------------------------------------------------------------------
-- Data sources (business / exchange systems)
-- ---------------------------------------------------------------------------
INSERT INTO sys.data_source_items (id, name_rus, name_eng, slug, descr, parent_id) VALUES
  ('b1000000-0000-0000-0000-000000000001'::uuid, 'ICE',        'ICE',        'ice',        'Intercontinental Exchange', NULL),
  ('b1000000-0000-0000-0000-000000000002'::uuid, 'CME Group',  'CME Group',  'cme',        'Chicago Mercantile Exchange Group', NULL),
  ('b1000000-0000-0000-0000-000000000003'::uuid, 'EEX',        'EEX',        'eex',        'European Energy Exchange', NULL),
  ('b1000000-0000-0000-0000-000000000004'::uuid, 'Nymex',      'NYMEX',      'nymex',      'New York Mercantile Exchange (CME)', 'b1000000-0000-0000-0000-000000000002'::uuid),
  ('b1000000-0000-0000-0000-000000000005'::uuid, 'Argus',      'Argus',      'argus',      'Argus Media price assessments', NULL)
ON CONFLICT (id) DO UPDATE SET
  name_rus = EXCLUDED.name_rus,
  name_eng = EXCLUDED.name_eng,
  slug = EXCLUDED.slug,
  descr = EXCLUDED.descr,
  parent_id = EXCLUDED.parent_id;

-- ---------------------------------------------------------------------------
-- Extraction sources
-- ---------------------------------------------------------------------------
INSERT INTO sys.data_extraction_sources (
  id, name, descr,
  extract_options, storage_options, load_options,
  schedule_id, data_source_id, parent_id
) VALUES

-- 1 ICE Brent options (email attachments)
(
  'c2000000-0000-0000-0000-000000000001'::uuid,
  'ICE Brent options',
  'Daily ICE Brent options settlement PDFs',
  '{"extract_type": 1, "attachment_patterns": ["ice_options_brent_*.pdf"], "subject_patterns": ["ICE Brent Options"]}'::jsonb,
  '{"path": "Открытые/ICE/options", "filename_template": "brent_${year}_${month}_${day}.pdf", "archive_path_template": "${year}/${month}"}'::jsonb,
  '{"handlers": [{"handler_type": "Python", "name": "ice_brent_options_loader", "module": "portal_lineage_fixtures.ice_brent_options_loader"}]}'::jsonb,
  NULL,
  'b1000000-0000-0000-0000-000000000001'::uuid,
  NULL
),

-- 2 ICE futures daily market reports
(
  'c2000000-0000-0000-0000-000000000002'::uuid,
  'ICE futures daily market reports',
  'ICE futures end-of-day market reports',
  '{"extract_type": 1, "attachment_patterns": ["ice_futures_dmr_*.csv"]}'::jsonb,
  '{"path": "Открытые/ICE/futures", "filename_template": "futures_${year}${month}${day}.csv", "archive_path_template": "${year}/${month}"}'::jsonb,
  '{"handlers": [{"handler_type": "Python", "name": "ice_futures_dmr_loader", "module": "portal_lineage_fixtures.ice_futures_dmr_loader"}]}'::jsonb,
  NULL,
  'b1000000-0000-0000-0000-000000000001'::uuid,
  NULL
),

-- 3 ICE COT reports
(
  'c2000000-0000-0000-0000-000000000003'::uuid,
  'ICE COT daily reports',
  'Commitments of Traders from ICE',
  '{"extract_type": 1, "attachment_patterns": ["ice_cot_*.xlsx"]}'::jsonb,
  '{"path": "Открытые/ICE/cot", "filename_template": "cot_${year}_${month}_${day}.xlsx", "archive_path_template": "${year}"}'::jsonb,
  '{"handlers": [{"handler_type": "Python", "name": "ice_cot_loader", "module": "portal_lineage_fixtures.ice_cot_loader"}]}'::jsonb,
  NULL,
  'b1000000-0000-0000-0000-000000000001'::uuid,
  NULL
),

-- 4 CME CL futures settlements
(
  'c2000000-0000-0000-0000-000000000004'::uuid,
  'CME CL futures settlements',
  'CME Group WTI crude futures settlements',
  '{"extract_type": 1, "attachment_patterns": ["cme_cl_settle_*.csv"], "subject_patterns": ["CME CL Settle"]}'::jsonb,
  '{"path": "Открытые/CME/CL", "filename_template": "cl_${year}${month}${day}.csv", "archive_path_template": "${year}/${month}"}'::jsonb,
  '{"handlers": [{"handler_type": "Python", "name": "cme_cl_loader", "module": "portal_lineage_fixtures.cme_cl_loader"}]}'::jsonb,
  NULL,
  'b1000000-0000-0000-0000-000000000002'::uuid,
  NULL
),

-- 5 CME NG natural gas
(
  'c2000000-0000-0000-0000-000000000005'::uuid,
  'CME NG settlements',
  'Henry Hub natural gas futures settlements',
  '{"extract_type": 1, "attachment_patterns": ["cme_ng_*.csv"]}'::jsonb,
  '{"path": "Открытые/CME/NG", "filename_template": "ng_${year}${month}${day}.csv", "archive_path_template": "${year}/${month}"}'::jsonb,
  '{"handlers": [{"handler_type": "Python", "name": "cme_ng_loader", "module": "portal_lineage_fixtures.cme_ng_loader"}]}'::jsonb,
  NULL,
  'b1000000-0000-0000-0000-000000000002'::uuid,
  NULL
),

-- 6 NYMEX (child of CME Group) — parent extraction optional later
(
  'c2000000-0000-0000-0000-000000000006'::uuid,
  'NYMEX RBOB gasoline',
  'NYMEX RBOB gasoline futures',
  '{"extract_type": 1, "attachment_patterns": ["nymex_rbob_*.csv"]}'::jsonb,
  '{"path": "Открытые/NYMEX/RBOB", "filename_template": "rbob_${year}${month}${day}.csv", "archive_path_template": "${year}/${month}"}'::jsonb,
  '{"handlers": [{"handler_type": "Python", "name": "nymex_rbob_loader", "module": "portal_lineage_fixtures.nymex_rbob_loader"}]}'::jsonb,
  NULL,
  'b1000000-0000-0000-0000-000000000004'::uuid,
  NULL
),

-- 7 EEX power spot
(
  'c2000000-0000-0000-0000-000000000007'::uuid,
  'EEX power spot',
  'EEX day-ahead power spot prices',
  '{"extract_type": 2, "filename_patterns": ["eex_power_dah_*.xml"]}'::jsonb,
  '{"path": "Открытые/EEX/power", "filename_template": "power_${year}_${month}_${day}.xml", "archive_path_template": "${year}/${month}"}'::jsonb,
  '{"handlers": [{"handler_type": "Python", "name": "eex_power_loader", "module": "portal_lineage_fixtures.eex_power_loader"}]}'::jsonb,
  NULL,
  'b1000000-0000-0000-0000-000000000003'::uuid,
  NULL
),

-- 8 EEX gas
(
  'c2000000-0000-0000-0000-000000000008'::uuid,
  'EEX gas spot',
  'EEX natural gas spot indices',
  '{"extract_type": 2, "filename_patterns": ["eex_gas_*.csv"]}'::jsonb,
  '{"path": "Открытые/EEX/gas", "filename_template": "gas_${year}${month}${day}.csv", "archive_path_template": "${year}"}'::jsonb,
  '{"handlers": [{"handler_type": "Python", "name": "eex_gas_loader", "module": "portal_lineage_fixtures.eex_gas_loader"}]}'::jsonb,
  NULL,
  'b1000000-0000-0000-0000-000000000003'::uuid,
  NULL
),

-- 9 Argus crude assessments
(
  'c2000000-0000-0000-0000-000000000009'::uuid,
  'Argus crude assessments',
  'Argus daily crude price assessments',
  '{"extract_type": 1, "attachment_patterns": ["argus_crude_*.xlsx"], "subject_patterns": ["Argus Crude"]}'::jsonb,
  '{"path": "Открытые/Argus/crude", "filename_template": "crude_${year}_${month}_${day}.xlsx", "archive_path_template": "${year}/${month}"}'::jsonb,
  '{"handlers": [{"handler_type": "Python", "name": "argus_crude_loader", "module": "portal_lineage_fixtures.argus_crude_loader"}]}'::jsonb,
  NULL,
  'b1000000-0000-0000-0000-000000000005'::uuid,
  NULL
),

-- 10 Argus products + dual Python handlers (primary + curated)
(
  'c2000000-0000-0000-0000-000000000010'::uuid,
  'Argus products assessments',
  'Argus refined products assessments (dual loader demo)',
  '{"extract_type": 1, "attachment_patterns": ["argus_products_*.xlsx"]}'::jsonb,
  '{"path": "Открытые/Argus/products", "filename_template": "products_${year}_${month}_${day}.xlsx", "archive_path_template": "${year}/${month}"}'::jsonb,
  '{"handlers": [
      {"handler_type": "Python", "name": "argus_products_py", "module": "portal_lineage_fixtures.argus_products_loader"},
      {"handler_type": "Python", "name": "argus_products_curated", "module": "portal_lineage_fixtures.argus_products_curated_loader"}
    ]}'::jsonb,
  NULL,
  'b1000000-0000-0000-0000-000000000005'::uuid,
  NULL
)

ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  descr = EXCLUDED.descr,
  extract_options = EXCLUDED.extract_options,
  storage_options = EXCLUDED.storage_options,
  load_options = EXCLUDED.load_options,
  data_source_id = EXCLUDED.data_source_id,
  parent_id = EXCLUDED.parent_id;

COMMIT;
