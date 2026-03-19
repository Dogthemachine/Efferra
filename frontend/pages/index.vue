<template>
  <div>
    <h1>{{ $t('welcome') }}</h1>
    <p>{{ $t('description') }}</p>
    <nav>
      <ul>
        <li v-for="locale in availableLocales" :key="locale.code">
          <NuxtLinkLocale :to="'/'" :locale="locale.code">
            {{ locale.name }}
          </NuxtLinkLocale>
        </li>
      </ul>
    </nav>
  </div>
</template>

<script setup lang="ts">
const { locales, locale: currentLocale } = useI18n()

const availableLocales = computed(() =>
  locales.value.filter(l => typeof l !== 'string' && l.code !== currentLocale.value)
)
</script>
