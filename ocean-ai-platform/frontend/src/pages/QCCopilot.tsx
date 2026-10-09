import {useEffect} from 'react';
import {useSearchParams} from 'react-router-dom';
import QCWorkspace from '../components/QCWorkspace';
import QCSample from './QCSample';
export default function QCCopilot() {
 const [search,setSearch]=useSearchParams(),sample=search.get('source')==='SAMPLE';
 useEffect(()=>{if(sample&&search.toString()!=='source=SAMPLE')setSearch(new URLSearchParams({source:'SAMPLE'}),{replace:true});},[sample,search,setSearch]);
 return sample?<QCSample variant="workspace"/>:<QCWorkspace/>;
}
