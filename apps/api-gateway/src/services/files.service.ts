import { Injectable } from '@nestjs/common';
import * as os from 'os';
import * as path from 'path';
import * as fs from 'fs';

@Injectable()
export class FilesService {
  private baseDataDir: string;
  constructor() {
    const appName = 'DevArchiveManager';
    const home = os.homedir();
    let base: string;
    switch (process.platform) {
      case 'win32':
        base = path.join(process.env.APPDATA || path.join(home, 'AppData', 'Roaming'), appName, 'data'); break;
      case 'darwin':
        base = path.join(home, 'Library', 'Application Support', appName, 'data'); break;
      default:
        base = path.join(home, '.config', appName, 'data');
    }
    this.baseDataDir = base;
    fs.mkdirSync(this.baseDataDir, { recursive: true });
  }
  ensureProjectDirs(projectId: string) {
    const base = path.join(this.baseDataDir, 'projects', projectId);
    const artifacts = path.join(base, 'artifacts');
    const logs = path.join(base, 'logs');
    const cache = path.join(base, 'cache');
    [base, artifacts, logs, cache].forEach(d => fs.mkdirSync(d, { recursive: true }));
    return { base, artifacts, logs, cache };
  }
  saveArtifact(projectId: string, filename: string, content: string | Buffer) {
    const dirs = this.ensureProjectDirs(projectId);
    const full = path.join(dirs.artifacts, filename);
    fs.writeFileSync(full, content);
    return full;
  }
}
