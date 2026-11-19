import { ArrowRightOutlined, DatabaseOutlined, SearchOutlined } from '@ant-design/icons';
import { Alert, Button, Empty, Select, Space, Spin, Tag, Typography, theme } from 'antd';
import { useNavigate } from 'react-router-dom';
import { LINEAGE_PICKER_TYPES, useCatalogLineagePicker } from '../queries';
import './overviewSearch.css';

const TYPE_ORDER = new Map(LINEAGE_PICKER_TYPES.map((type, index) => [type, index]));

const OverviewSearch = () => {
  const navigate = useNavigate();
  const { token } = theme.useToken();
  const pickerQueries = useCatalogLineagePicker();
  const isLoading = pickerQueries.some((query) => query.isPending);
  const hasError = pickerQueries.some((query) => query.isError);
  const options = pickerQueries.flatMap((query) =>
    (query.data?.items ?? []).map((item) => ({
      value: item.id,
      type: item.asset_type,
      name: item.display_name || item.name || item.qualified_name,
      qualifiedName: item.qualified_name,
      label: `[${item.asset_type}] ${item.display_name || item.name || item.qualified_name}`,
    }))
  ).sort((a, b) => {
    const typeDiff = (TYPE_ORDER.get(a.type as (typeof LINEAGE_PICKER_TYPES)[number]) ?? 99)
      - (TYPE_ORDER.get(b.type as (typeof LINEAGE_PICKER_TYPES)[number]) ?? 99);
    return typeDiff || a.label.localeCompare(b.label);
  });

  return (
    <section
      className="overview-search"
      aria-labelledby="overview-search-title"
      style={{
        background: `radial-gradient(ellipse at top right, ${token.colorPrimaryBg}, transparent 70%), ${token.colorBgContainer}`,
        borderColor: token.colorPrimaryBorder,
        boxShadow: token.boxShadowTertiary,
      }}
    >
      <div className="overview-search__eyebrow" style={{ color: token.colorPrimary }}>
        <DatabaseOutlined /> EXPLORE YOUR DWH
      </div>
      <Typography.Title id="overview-search-title" level={3} className="overview-search__title">
        Все начинается с поиска
      </Typography.Title>
      <Typography.Paragraph type="secondary" className="overview-search__description">
        Найдите источник, таблицу или процесс — и проследите путь данных в Lineage.
      </Typography.Paragraph>
      <div className="overview-search__field" style={{ boxShadow: token.boxShadowTertiary }}>
        <SearchOutlined className="overview-search__icon" style={{ color: token.colorPrimary }} aria-hidden />
        <Select
          className="overview-search__select"
          aria-label="Поиск объекта DWH для перехода в Lineage"
          aria-describedby="overview-search-hint"
          showSearch
          allowClear
          size="large"
          optionFilterProp="label"
          placeholder="Название источника, таблицы или процесса…"
          options={options}
          value={undefined}
          loading={pickerQueries.some((query) => query.isFetching)}
          listHeight={320}
          onSelect={(value) => navigate(`/lineage/${value}`)}
          optionRender={(option) => (
            <div className="overview-search__option">
              <Space size={8}>
                <Tag color="blue">{option.data.type}</Tag>
                <Typography.Text strong ellipsis>{option.data.name}</Typography.Text>
              </Space>
              <Typography.Text type="secondary" ellipsis className="overview-search__qualified-name">
                {option.data.qualifiedName}
              </Typography.Text>
            </div>
          )}
          notFoundContent={isLoading ? (
            <Space><Spin size="small" /> Загрузка объектов…</Space>
          ) : hasError ? (
            'Список недоступен. Попробуйте повторить загрузку.'
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Объекты не найдены" />
          )}
        />
      </div>
      <div className="overview-search__footer">
        <Typography.Text id="overview-search-hint" type="secondary">Выберите объект, чтобы открыть его связи и зависимости</Typography.Text>
        <Button type="link" onClick={() => navigate('/lineage')}>
          Обзор Lineage <ArrowRightOutlined />
        </Button>
      </div>
      {hasError ? (
        <Alert
          type="warning"
          showIcon
          message="Часть объектов не удалось загрузить. Результаты поиска могут быть неполными."
          action={<Button size="small" onClick={() => {
            pickerQueries.filter((query) => query.isError).forEach((query) => { void query.refetch(); });
          }}>Повторить</Button>}
        />
      ) : null}
    </section>
  );
};

export default OverviewSearch;
