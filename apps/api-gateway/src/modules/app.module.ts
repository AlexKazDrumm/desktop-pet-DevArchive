import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ProjectsModule } from './projects/projects.module.js';
import { PrismaService } from '../services/prisma.service.js';
import { FilesService } from '../services/files.service.js';

@Module({
  imports: [ConfigModule.forRoot({ isGlobal: true }), ProjectsModule],
  providers: [PrismaService, FilesService]
})
export class AppModule {}
