import { Module } from '@nestjs/common';
import { ProjectsController } from './projects.controller.js';
import { ProjectsService } from './projects.service.js';
import { PrismaService } from '../../services/prisma.service.js';
import { FilesService } from '../../services/files.service.js';

@Module({ controllers: [ProjectsController], providers: [ProjectsService, PrismaService, FilesService] })
export class ProjectsModule {}
