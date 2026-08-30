import { Injectable, NotFoundException } from '@nestjs/common';
import axios from 'axios';
import { JobKind, JobStatus } from '@prisma/client';
import { PrismaService } from '../../services/prisma.service.js';
import { FilesService } from '../../services/files.service.js';
import { CreateProjectDto, UpdateProjectDto } from './dto.js';

@Injectable()
export class ProjectsService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly files: FilesService
  ) {}

  async create(dto: CreateProjectDto) {
    const project = await this.prisma.project.create({
      data: {
        name: dto.name,
        kind: dto.kind,
        context: dto.context,
        localPath: dto.localPath,
        notes: dto.notes,
        links: dto.links ? { create: dto.links } : undefined,
        components: dto.components
          ? {
              create: dto.components.map((component) => ({
                role: component.role,
                name: component.name,
                localPath: component.localPath,
                notes: component.notes,
                links: component.links ? { create: component.links } : undefined
              }))
            }
          : undefined
      },
      include: { components: { include: { links: true } }, links: true }
    });
    this.files.ensureProjectDirs(project.id);
    return project;
  }

  list(q?: string) {
    return this.prisma.project.findMany({
      where: q
        ? {
            OR: [
              { name: { contains: q, mode: 'insensitive' } },
              { notes: { contains: q, mode: 'insensitive' } }
            ]
          }
        : undefined,
      orderBy: { createdAt: 'desc' },
      include: { components: true, links: true }
    });
  }

  async get(id: string) {
    const project = await this.prisma.project.findUnique({
      where: { id },
      include: {
        components: { include: { links: true } },
        links: true,
        artifacts: true,
        scans: true
      }
    });
    if (!project) throw new NotFoundException('Project not found');
    return project;
  }

  async update(id: string, dto: UpdateProjectDto) {
    await this.get(id);
    return this.prisma.project.update({
      where: { id },
      data: {
        name: dto.name,
        kind: dto.kind,
        context: dto.context,
        localPath: dto.localPath,
        notes: dto.notes
      }
    });
  }

  async enqueueScan(id: string, kind: 'SNAP_SCAN' | 'SNAP_CONCAT') {
    const project = await this.get(id);
    const root = project.localPath || project.components[0]?.localPath;
    const scan = await this.prisma.scan.create({
      data: {
        projectId: id,
        kind: kind as JobKind,
        status: 'RUNNING',
        startedAt: new Date()
      }
    });

    if (!root) {
      await this.prisma.scan.update({
        where: { id: scan.id },
        data: {
          status: 'FAILED',
          finishedAt: new Date(),
          resultJson: { error: 'No localPath specified' }
        }
      });
      return { scanId: scan.id, status: 'FAILED' as JobStatus, error: 'No localPath' };
    }

    let status: JobStatus = 'SUCCEEDED';
    try {
      const baseUrl = process.env.PY_SNAP_URL || 'http://127.0.0.1:8801';
      const endpoint = kind === 'SNAP_SCAN' ? '/scan' : '/concat';
      const { data } = await axios.post(
        baseUrl + endpoint,
        { rootDir: root },
        { timeout: 120_000 }
      );
      const prefix = kind === 'SNAP_SCAN' ? 'tree' : 'concat';
      const filename = `${prefix}-${Date.now()}.txt`;
      const fullPath = this.files.saveArtifact(id, filename, data.text || '');

      await this.prisma.artifact.create({
        data: {
          projectId: id,
          kind: `${prefix}.txt`,
          filePath: fullPath,
          metaJson: data.meta
        }
      });
      await this.prisma.scan.update({
        where: { id: scan.id },
        data: { status, finishedAt: new Date() }
      });
    } catch (error: unknown) {
      status = 'FAILED';
      const message = axios.isAxiosError(error)
        ? error.response?.data?.detail || error.message
        : error instanceof Error
          ? error.message
          : 'Unknown error';
      await this.prisma.scan.update({
        where: { id: scan.id },
        data: {
          status,
          finishedAt: new Date(),
          resultJson: { error: message }
        }
      });
    }

    return { scanId: scan.id, status };
  }
}
