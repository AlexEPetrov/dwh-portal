import { useParams } from 'react-router-dom';
import LineageWorkspace from '../components/LineageWorkspace';

/** Route parameters are the only standalone-page concern. */
const LineagePage = () => {
  const { assetId } = useParams<{ assetId: string }>();
  return <LineageWorkspace assetId={assetId} />;
};

export default LineagePage;
