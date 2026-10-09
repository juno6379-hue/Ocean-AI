import {readFileSync,existsSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';
export const dataURL=code=>'data:text/javascript;base64,'+Buffer.from(code).toString('base64');
const cache=new Map();
export function compile(path){
 if(cache.has(path))return cache.get(path);
 if(path.endsWith('client.ts')){const url=dataURL("export const API_BASE_URL='/api';export const apiFetch=()=>{throw new Error('PRODUCTION_AUTH_CLIENT_FORBIDDEN_IN_SAMPLE');};");cache.set(path,url);return url;}
 const result=ts.transpileModule(readFileSync(path,'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2023,jsx:ts.JsxEmit.ReactJSX}}).outputText,parsed=ts.createSourceFile(path,result,ts.ScriptTarget.ES2023,true,ts.ScriptKind.JS);let output=result;
 for(const statement of [...parsed.statements].reverse())if(ts.isImportDeclaration(statement)){const specifier=statement.moduleSpecifier.text;if(specifier.endsWith('.css')){output=output.slice(0,statement.getStart(parsed))+output.slice(statement.end);continue;}const base=resolve(dirname(path),specifier),found=specifier.startsWith('.')?[base,base+'.ts',base+'.tsx'].find(existsSync):null,url=specifier.startsWith('.')?compile(found):import.meta.resolve(specifier);output=output.slice(0,statement.moduleSpecifier.getStart(parsed))+JSON.stringify(url)+output.slice(statement.moduleSpecifier.end);}
 const url=dataURL(output);cache.set(path,url);return url;
}
export const frontend=fileURLToPath(new URL('../src/',import.meta.url));
