import { SchemaVersion } from "./schema";

export class SchemaRegistry {
  private versions: SchemaVersion[] = [];

  add(schema: SchemaVersion) {
    this.versions.push(schema);
  }

  latest(): SchemaVersion {
    return this.versions[this.versions.length - 1];
  }
}
