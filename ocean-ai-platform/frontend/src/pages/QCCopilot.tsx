import {useEffect} from 'react';
import {useSearchParams} from 'react-router-dom';
import QCWorkspace from '../components/QCWorkspace';
import QCSample from './QCSample';
import {canonicalWorkspaceSearch,workspaceDataMode} from '../data/workspaceMode';
export default function QCCopilot() {
 const [search,setSearch]=useSearchParams(),sample=workspaceDataMode(search)==='SAMPLE',canonical=canonicalWorkspaceSearch(search).toString();
 useEffect(()=>{if(search.toString()!==canonical)setSearch(canonical,{replace:true});},[canonical,search,setSearch]);
 return sample?<QCSample variant="workspace"/>:<QCWorkspace/>;
}
