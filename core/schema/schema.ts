export type SchemaVersion = {
  version: number;
  tables: Record<string, TableSchema>;
};

export type TableSchema = {
  name: string;
  fields: Record<string, string>;
};
