// Transpile the real relative dependency closure; no AEGIS boundary doubles.
import {readFileSync, writeFileSync, mkdirSync, mkdtempSync, rmSync} from 'node:fs';
import {dirname, resolve, relative, sep} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
const ts = createRequire(import.meta.url)('typescript');
const sourceRoot = fileURLToPath(new URL('../../src/', import.meta.url));

export async function loadRepositoryTypescript(entries) {
  const temp = mkdtempSync(resolve(tmpdir(), 'aegis-native-integration-'));
  const sources = new Map();
  writeFileSync(resolve(temp, 'package.json'), '{"type":"module"}\n');
  function emit(source) {
    const path = relative(sourceRoot, source);
    if (path.startsWith(`..${sep}`) || path === '..' || !path.endsWith('.ts')) {
      throw new Error(`source outside AEGIS TypeScript root: ${path}`);
    }
    const output = resolve(temp, path.replace(/\.ts$/, '.js'));
    if (sources.has(path)) return output;
    const bytes = readFileSync(source);
    sources.set(path, createHash('sha256').update(bytes).digest('hex'));
    const compiled = ts.transpileModule(bytes.toString('utf8'), {
      fileName: source, reportDiagnostics: true,
      compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022},
    });
    const errors = (compiled.diagnostics ?? []).filter(d => d.category === ts.DiagnosticCategory.Error);
    if (errors.length) throw new Error(ts.formatDiagnosticsWithColorAndContext(errors, {
      getCanonicalFileName: x => x, getCurrentDirectory: () => sourceRoot, getNewLine: () => '\n',
    }));
    const imports = ts.preProcessFile(compiled.outputText, true, true).importedFiles;
    for (const {fileName: specifier} of imports) {
      if (specifier.startsWith('node:')) continue;
      if (!specifier.startsWith('.') || !specifier.endsWith('.js')) {
        throw new Error(`unreviewed static runtime dependency: ${specifier}`);
      }
      emit(resolve(dirname(source), specifier.replace(/\.js$/, '.ts')));
    }
    mkdirSync(dirname(output), {recursive: true});
    writeFileSync(output, compiled.outputText);
    return output;
  }
  try {
    const modules = {};
    for (const entry of entries) modules[entry] = await import(pathToFileURL(emit(resolve(sourceRoot, entry))).href);
    return {modules, sources, cleanup: () => rmSync(temp, {recursive: true, force: true})};
  } catch (error) {
    rmSync(temp, {recursive: true, force: true});
    throw error;
  }
}
