import { Body, Controller, Get, Param, Patch, Post, Query } from '@nestjs/common';
import { ProjectsService } from './projects.service.js';
import { CreateProjectDto, UpdateProjectDto } from './dto.js';

@Controller('projects')
export class ProjectsController {
  constructor(private readonly svc: ProjectsService) {}

  @Post() create(@Body() dto: CreateProjectDto) { return this.svc.create(dto); }
  @Get() list(@Query('q') q?: string) { return this.svc.list(q); }
  @Get(':id') get(@Param('id') id: string) { return this.svc.get(id); }
  @Patch(':id') update(@Param('id') id: string, @Body() dto: UpdateProjectDto) { return this.svc.update(id, dto); }

  @Post(':id/scan') scan(@Param('id') id: string) { return this.svc.enqueueScan(id, 'SNAP_SCAN'); }
  @Post(':id/concat') concat(@Param('id') id: string) { return this.svc.enqueueScan(id, 'SNAP_CONCAT'); }
}
