// Внимание - нужно чтобы openapi.json уже был в папке
import { createClient } from '@hey-api/openapi-ts';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function generate() {
  await createClient({
    input: path.resolve(__dirname, '../../../common/contracts/openapi/openapi.json'),
    output: path.resolve(__dirname, '../src/shared/api/generated'),
    // Installed openapi-ts 0.46 uses `client`, not the newer plugin API.
    // Keep the cancellable Fetch service surface and existing operation names.
    client: 'fetch',
  });
}

generate().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
