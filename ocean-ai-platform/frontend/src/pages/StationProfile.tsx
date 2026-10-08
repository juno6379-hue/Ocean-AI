import LakeExplorer from '../components/LakeExplorer';
import { useParams } from 'react-router-dom';
export default function StationProfile() { const {id}=useParams(); return <LakeExplorer mode="detail" station={id}/>; }
