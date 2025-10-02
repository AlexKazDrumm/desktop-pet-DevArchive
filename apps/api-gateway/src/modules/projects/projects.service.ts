import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../services/prisma.service.js';
import { FilesService } from '../../services/files.service.js';
import { CreateProjectDto, UpdateProjectDto } from './dto.js';
import axios from 'axios';
import { JobKind } from '@prisma/client';

@Injectable()
export class ProjectsService {
  constructor(private prisma: PrismaService, private files: FilesService) {}

  async create(dto: CreateProjectDto) {
    const project = await this.prisma.project.create({
      data: {
        name: dto.name,
        kind: dto.kind,
        context: dto.context,
        localPath: dto.localPath,
        notes: dto.notes,
        links: dto.links ? { create: dto.links } : undefined,
        components: dto.components ? {
          create: dto.components.map(c => ({
            role: c.role, name: c.name, localPath: c.localPath, notes: c.notes,
            links: c.links ? { create: c.links } : undefined
          }))
        } : undefined
      },
      include: { components: { include: { links: true } }, links: true }
    });
    this.files.ensureProjectDirs(project.id);
    return project;
  }

  list(q?: string) {
    return this.prisma.project.findMany({
      where: q ? { OR: [{ name: { contains: q, mode: 'insensitive' } }, { notes: { contains: q, mode: 'insensitive' } }] } : undefined,
      orderBy: { createdAt: 'desc' },
      include: { components: true, links: true }
    });
  }

  async get(id: string) {
    const p = await this.prisma.project.findUnique({ where: { id }, include: { components: { include: { links: true } }, links: true, artifacts: true, scans: true } });
    if (!p) throw new NotFoundException('Project not found');
    return p;
  }

  async update(id: string, dto: UpdateProjectDto) {
    await this.get(id);
    return this.prisma.project.update({
      where: { id },
      data: { name: dto.name, kind: dto.kind, context: dto.context, localPath: dto.localPath, notes: dto.notes }
    });
  }

  async enqueueScan(id: string, kind: 'SNAP_SCAN'|'SNAP_CONCAT') {
    const project = await this.get(id);
    const root = project.localPath || project.components[0]?.localPath;
    const scan = await this.prisma.scan.create({ data: { projectId: id, kind: kind as JobKind, status: 'RUNNING', startedAt: new Date() } });
    if (!root) {
      await this.prisma.scan.update({ where: { id: scan.id }, data: { status: 'FAILED', finishedAt: new Date(), resultJson: { error: 'No localPath specified' } } });
      return { scanId: scan.id, error: 'No localPath' };
    }
    try {
      const base = process.env.PY_SNAP_URL || 'http://127.0.0.1:8801';
      if (kind === 'SNAP_SCAN') {
        const { data } = await axios.post(base + '/scan', { rootDir: root });
        const filename = `tree-${Date.now()}.txt`; const full = this.files.saveArtifact(id, filename, data.text || '');
        await this.prisma.artifact.create({ data: { projectId: id, kind: 'tree.txt', filePath: full, metaJson: data.meta } });
      } else {
        const { data } = await axios.post(base + '/concat', { rootDir: root });
        const filename = `concat-${Date.now()}.txt`; const full = this.files.saveArtifact(id, filename, data.text || '');
        await this.prisma.artifact.create({ data: { projectId: id, kind: 'concat.txt', filePath: full, metaJson: data.meta } });
      }
      await this.prisma.scan.update({ where: { id: scan.id }, data: { status: 'SUCCEEDED', finishedAt: new Date() } });
    } catch (e: any) {
      await this.prisma.scan.update({ where: { id: scan.id }, data: { status: 'FAILED', finishedAt: new Date(), resultJson: { error: e?.message } } });
    }
    return { scanId: scan.id, status: 'ENQUEUED' };
  }
}
