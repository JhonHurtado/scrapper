/**
 * Seed de sitios turísticos de Colombia para el schema Prisma (Place/Category).
 *
 * Uso (en el proyecto donde vive tu schema.prisma):
 *   1. Copia este archivo a prisma/seed.ts y output/prisma/seed-data.json a prisma/seed-data.json
 *   2. En package.json:  "prisma": { "seed": "ts-node prisma/seed.ts" }
 *   3. npx prisma db seed
 */
import { PrismaClient, PlaceStatus, Role } from "@prisma/client";
import data from "./seed-data.json";

const prisma = new PrismaClient();

// Dueño de los lugares importados (Place.ownerId es obligatorio)
const OWNER_EMAIL = process.env.SEED_OWNER_EMAIL ?? "turismo@sistema.local";

async function main() {
  const owner = await prisma.user.upsert({
    where: { email: OWNER_EMAIL },
    update: {},
    create: {
      email: OWNER_EMAIL,
      firstName: "Sistema",
      lastName: "Turismo",
      role: Role.ADMIN,
      emailVerified: true,
    },
  });

  const categoryIdByKey: Record<string, string> = {};
  for (const c of data.categories) {
    const cat = await prisma.category.upsert({
      where: { slug: c.slug },
      update: {},
      create: { name: c.name, slug: c.slug, icon: c.icon },
    });
    categoryIdByKey[c.key] = cat.id;
  }

  let created = 0;
  for (const p of data.places) {
    await prisma.place.upsert({
      where: { slug: p.slug },
      update: {},
      create: {
        name: p.name,
        slug: p.slug,
        description: p.description,
        shortDescription: p.shortDescription,
        address: p.address,
        city: p.city,
        department: p.department,
        country: p.country,
        latitude: p.latitude,
        longitude: p.longitude,
        mainImage: p.mainImage,
        phone: p.phone,
        email: p.email,
        website: p.website,
        moderationStatus: PlaceStatus.APPROVED,
        ownerId: owner.id,
        categories: {
          create: [{ categoryId: categoryIdByKey[p.category] }],
        },
        images: p.mainImage
          ? { create: [{ url: p.mainImage, isPrimary: true, order: 0 }] }
          : undefined,
      },
    });
    created++;
  }

  console.log(`Seed completado: ${created} lugares, ${data.categories.length} categorías`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
