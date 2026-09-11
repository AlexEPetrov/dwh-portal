// Внимание - нужно чтобы openapi.json уже был в папке
import { createClient } from '@hey-api/openapi-ts';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function generate() {
  await createClient({
    input: path.resolve(__dirname, '../../../common/contracts/openapi/openapi.json'),
    output: path.resolve(__dirname, '../src/shared/api/generated'),
    plugins: ['@hey-api/client-axios'],
  });
}

generate().catch(console.error);