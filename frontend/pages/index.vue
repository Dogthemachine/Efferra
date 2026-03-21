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

    <hr>
    <section>
      <h2>{{ $t('backendStatus') }}</h2>
      <p v-if="healthPending">{{ $t('backendLoading') }}</p>
      <p v-else-if="healthError">{{ $t('backendError') }}: {{ healthError.message }}</p>
      <p v-else>{{ $t('backendResult') }}: {{ healthData?.status }}</p>
    </section>
  </div>
</template>

<script setup lang="ts">
const { locales, locale: currentLocale } = useI18n()

const availableLocales = computed(() =>
  locales.value.filter(l => typeof l !== 'string' && l.code !== currentLocale.value)
)

const { data: healthData, pending: healthPending, error: healthError } = useFetch<{ status: string }>('/api/health/', {
  server: false,
})
</script>
