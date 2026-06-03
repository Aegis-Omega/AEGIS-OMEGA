export const GPU_BUFFER_USAGE = {
  MAP_READ:      0x0001 as GPUBufferUsageFlags,
  MAP_WRITE:     0x0002 as GPUBufferUsageFlags,
  COPY_SRC:      0x0004 as GPUBufferUsageFlags,
  COPY_DST:      0x0008 as GPUBufferUsageFlags,
  INDEX:         0x0010 as GPUBufferUsageFlags,
  VERTEX:        0x0020 as GPUBufferUsageFlags,
  UNIFORM:       0x0040 as GPUBufferUsageFlags,
  STORAGE:       0x0080 as GPUBufferUsageFlags,
  INDIRECT:      0x0100 as GPUBufferUsageFlags,
  QUERY_RESOLVE: 0x0200 as GPUBufferUsageFlags,
} as const

export const GPU_TEXTURE_USAGE = {
  COPY_SRC:          0x01 as GPUTextureUsageFlags,
  COPY_DST:          0x02 as GPUTextureUsageFlags,
  TEXTURE_BINDING:   0x04 as GPUTextureUsageFlags,
  STORAGE_BINDING:   0x08 as GPUTextureUsageFlags,
  RENDER_ATTACHMENT: 0x10 as GPUTextureUsageFlags,
} as const
