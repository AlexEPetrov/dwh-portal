import { ArrowRightOutlined, DatabaseOutlined, SearchOutlined } from '@ant-design/icons';
import { Alert, Button, Empty, Select, Space, Spin, Tag, Typography, theme } from 'antd';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCatalogAssets } from '../queries';
import { overviewSearchParams, overviewSearchUrl } from '../search';
import './overviewSearch.css';

const OverviewSearch = () => {
  const navigate = useNavigate();
  const { token } = theme.useToken();
  const [searchText, setSearchText] = useState('');
  const [queryText, setQueryText] = useState('');
  const currentText = searchText.trim();
  const isDebouncing = currentText !== queryText;
  useEffect(() => {
    const timer = setTimeout(() => setQueryText(currentText), 300);
    return () => clearTimeout(timer);
  }, [currentText]);
  const assetsQuery = useCatalogAssets(overviewSearchParams(queryText), !isDebouncing);
  const isLoading = isDebouncing || assetsQuery.isPending || assetsQuery.isFetching;
  const hasError = !isDebouncing && assetsQuery.isError;
  // Never offer selectable results for text that the user has already replaced.
  const options = (isDebouncing ? [] : assetsQuery.data?.items ?? []).map((item) => ({
      value: item.id,
      type: item.asset_type,
      name: item.display_name || item.name || item.qualified_name,
      qualifiedName: item.qualified_name,
      description: item.description ?? '',
      label: `[${item.asset_type}] ${item.display_name || item.name || item.qualified_name}`,
    }));
  const total = isDebouncing ? undefined : assetsQuery.data?.total;

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
        <DatabaseOutlined /> АНАЛИЗИРУЙ
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
          filterOption={false}
          searchValue={searchText}
          onSearch={setSearchText}
          onClear={() => setSearchText('')}
          placeholder="Название или описание объекта во всём каталоге…"
          options={options}
          value={undefined}
          loading={isLoading}
          listHeight={320}
          onSelect={(value) => {
            if (!isDebouncing) navigate(`/lineage/${value}`);
          }}
          optionRender={(option) => (
            <div className="overview-search__option">
              <Space size={8}>
                <Tag color="blue">{option.data.type}</Tag>
                <Typography.Text strong ellipsis>{option.data.name}</Typography.Text>
              </Space>
              <Typography.Text type="secondary" ellipsis className="overview-search__qualified-name">
                {option.data.qualifiedName}
              </Typography.Text>
              {option.data.description ? (
                <Typography.Text type="secondary" ellipsis className="overview-search__qualified-name">
                  {option.data.description}
                </Typography.Text>
              ) : null}
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
      <Space wrap>
        <Typography.Text type="secondary">
          {total === undefined ? 'Поиск по всему каталогу' : `Показано ${options.length} из ${total}`}
        </Typography.Text>
        <Button type="link" onClick={() => navigate(overviewSearchUrl(searchText))}>
          Все результаты <ArrowRightOutlined />
        </Button>
      </Space>
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
          message="Не удалось выполнить поиск по каталогу."
          action={<Button size="small" onClick={() => {
            void assetsQuery.refetch();
          }}>Повторить</Button>}
        />
      ) : null}
    </section>
  );
};

export default OverviewSearch;
