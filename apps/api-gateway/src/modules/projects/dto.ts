import { IsArray, IsEnum, IsNotEmpty, IsOptional, IsString, IsUrl, ValidateNested } from 'class-validator';
import { Type } from 'class-transformer';
import { ProjectKind, ProjectContext, ComponentRole, LinkType } from '@prisma/client';

export class CreateLinkDto {
  @IsEnum(LinkType) type!: LinkType;
  @IsString() @IsUrl() url!: string;
  @IsOptional() @IsString() label?: string;
}
export class CreateComponentDto {
  @IsEnum(ComponentRole) role!: ComponentRole;
  @IsOptional() @IsString() name?: string;
  @IsOptional() @IsString() localPath?: string;
  @IsOptional() @IsString() notes?: string;
  @IsOptional() @IsArray() @ValidateNested({ each: true }) @Type(()=>CreateLinkDto) links?: CreateLinkDto[];
}
export class CreateProjectDto {
  @IsString() @IsNotEmpty() name!: string;
  @IsEnum(ProjectKind) kind!: ProjectKind;
  @IsOptional() @IsEnum(ProjectContext) context?: ProjectContext;
  @IsOptional() @IsString() localPath?: string;
  @IsOptional() @IsString() notes?: string;
  @IsOptional() @IsArray() @ValidateNested({ each: true }) @Type(()=>CreateLinkDto) links?: CreateLinkDto[];
  @IsOptional() @IsArray() @ValidateNested({ each: true }) @Type(()=>CreateComponentDto) components?: CreateComponentDto[];
}
export class UpdateProjectDto {
  @IsOptional() @IsString() @IsNotEmpty() name?: string;
  @IsOptional() @IsEnum(ProjectKind) kind?: ProjectKind;
  @IsOptional() @IsEnum(ProjectContext) context?: ProjectContext;
  @IsOptional() @IsString() localPath?: string;
  @IsOptional() @IsString() notes?: string;
}
