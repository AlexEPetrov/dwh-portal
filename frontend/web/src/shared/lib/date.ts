import dayjs from 'dayjs';

export const formatDate = (date: string | Date, format = 'DD.MM.YYYY') => {
  return dayjs(date).format(format);
};

export const getDateRange = (start: string, end: string) => {
  const dates = [];
  let current = dayjs(start);
  const endDate = dayjs(end);
  while (current.isBefore(endDate) || current.isSame(endDate)) {
    dates.push(current.format('YYYY-MM-DD'));
    current = current.add(1, 'day');
  }
  return dates;
};
