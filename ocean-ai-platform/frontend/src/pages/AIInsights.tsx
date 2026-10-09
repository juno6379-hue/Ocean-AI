import {useEffect} from 'react';
import {useSearchParams} from 'react-router-dom';
import AnalysisWorkspace from '../components/AnalysisWorkspace';
import AIInsightsSample from './AIInsightsSample';
import {canonicalWorkspaceSearch,workspaceDataMode} from '../data/workspaceMode';
export default function AIInsights(){
 const [search,setSearch]=useSearchParams(),sample=workspaceDataMode(search)==='SAMPLE',canonical=canonicalWorkspaceSearch(search).toString();
 useEffect(()=>{if(search.toString()!==canonical)setSearch(canonical,{replace:true});},[canonical,search,setSearch]);
 return sample?<AIInsightsSample/>:<AnalysisWorkspace insights/>;
}
