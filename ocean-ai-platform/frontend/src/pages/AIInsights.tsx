import {useEffect} from 'react';
import {useSearchParams} from 'react-router-dom';
import AnalysisWorkspace from '../components/AnalysisWorkspace';
import AIInsightsSample from './AIInsightsSample';
export default function AIInsights(){
 const [search,setSearch]=useSearchParams(),sample=search.get('source')==='SAMPLE';
 useEffect(()=>{if(sample&&search.toString()!=='source=SAMPLE')setSearch(new URLSearchParams({source:'SAMPLE'}),{replace:true});},[sample,search,setSearch]);
 return sample?<AIInsightsSample/>:<AnalysisWorkspace insights/>;
}
