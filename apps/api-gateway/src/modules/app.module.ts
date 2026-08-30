import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ProjectsModule } from './projects/projects.module.js';

@Module({
  imports: [ConfigModule.forRoot({ isGlobal: true }), ProjectsModule]
})
export class AppModule {}
