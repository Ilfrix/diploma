"""
Скрипт для нагрузочного тестирования API
Измеряет время выполнения для разных объемов данных
С многократными итерациями для стабильности результатов
"""

import time
import os
import json
import statistics
import uuid
from datetime import datetime
from typing import List, Dict
import requests
from PIL import Image, ImageDraw
import io
import matplotlib.pyplot as plt
import numpy as np
import threading

# Конфигурация
API_BASE_URL = "http://localhost:8000"
TEST_USER = {
    "username": "load_test_user",
    "email": "load_test@example.com",
    "password": "testpassword123"
}


class LoadTester:
    def __init__(self):
        self.access_token = None
        self.lock = threading.Lock()
        
    def login(self) -> bool:
        """Авторизация и получение токена"""
        response = requests.post(
            f"{API_BASE_URL}/api/login",
            json={
                "username": TEST_USER["username"],
                "password": TEST_USER["password"]
            }
        )
        if response.status_code == 200:
            self.access_token = response.json()["access_token"]
            print("✓ Авторизация успешна")
            return True
        else:
            print(f"✗ Ошибка авторизации: {response.status_code}")
            return False
    
    def register_if_needed(self) -> bool:
        """Регистрация тестового пользователя"""
        response = requests.post(
            f"{API_BASE_URL}/api/register",
            json=TEST_USER
        )
        if response.status_code == 201:
            print("✓ Зарегистрирован новый тестовый пользователь")
            return True
        elif response.status_code == 400:
            print("⚠ Пользователь уже существует, пробуем войти")
            return self.login()
        else:
            print(f"✗ Ошибка регистрации: {response.status_code}")
            return False
    
    def create_unique_image(self, index: int) -> bytes:
        """Создание уникального тестового изображения"""
        size = (800 + (index % 400), 600 + (index % 300))
        
        r = (index * 13) % 256
        g = (index * 37) % 256
        b = (index * 73) % 256
        color = (r, g, b)
        
        img = Image.new('RGB', size, color=color)
        draw = ImageDraw.Draw(img)
        text = f"Sample_{index}_{uuid.uuid4().hex[:8]}"
        position = (50 + (index % 100), 50 + (index % 100))
        draw.text(position, text, fill=(255 - r, 255 - g, 255 - b))
        
        if index % 2 == 0:
            x1 = 100 + (index % 200)
            y1 = 100 + (index % 200)
            x2 = x1 + 100 + (index % 100)
            y2 = y1 + 100 + (index % 100)
            draw.rectangle([x1, y1, x2, y2], outline=(255, 255, 255), width=3)
        else:
            x = 400 + (index % 200)
            y = 300 + (index % 150)
            r_radius = 50 + (index % 50)
            draw.ellipse([x - r_radius, y - r_radius, x + r_radius, y + r_radius], 
                        outline=(255, 255, 255), width=3)
        
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG', quality=85)
        img_byte_arr.seek(0)
        return img_byte_arr.getvalue()
    
    def create_sample(self, name: str, image_bytes: bytes, retry_count: int = 2) -> Dict:
        """Создание одного сэмпла с повторами при ошибках"""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        files = {
            "image": ("test.jpg", image_bytes, "image/jpeg")
        }
        data = {
            "name": name,
            "description": f"Test sample {name}"
        }
        
        for attempt in range(retry_count):
            try:
                start_time = time.time()
                response = requests.post(
                    f"{API_BASE_URL}/api/samples",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=30
                )
                elapsed_time = time.time() - start_time
                
                if response.status_code == 202:
                    return {
                        "success": True,
                        "sample_id": response.json().get("id"),
                        "time": elapsed_time,
                        "status_code": response.status_code
                    }
                elif response.status_code == 409:
                    return {
                        "success": False,
                        "error": "Duplicate image",
                        "status_code": response.status_code,
                        "time": elapsed_time
                    }
                else:
                    if attempt < retry_count - 1:
                        time.sleep(0.5)
                        continue
                    return {
                        "success": False,
                        "error": response.text[:100],
                        "status_code": response.status_code,
                        "time": elapsed_time
                    }
            except requests.exceptions.Timeout:
                if attempt < retry_count - 1:
                    time.sleep(1)
                    continue
                return {
                    "success": False,
                    "error": "Timeout",
                    "time": 30
                }
            except Exception as e:
                if attempt < retry_count - 1:
                    time.sleep(0.5)
                    continue
                return {
                    "success": False,
                    "error": str(e)[:100],
                    "time": 0
                }
        
        return {"success": False, "error": "Max retries exceeded"}
    
    def create_samples_batch(self, count: int, delay_between: float = 0.05) -> Dict:
        """Создание пакета сэмплов с задержкой между запросами"""
        results = []
        successful = 0
        failed = 0
        total_time_sum = 0
        
        for i in range(count):
            image_bytes = self.create_unique_image(i + int(time.time() * 1000) % 10000)
            
            result = self.create_sample(f"Test_Sample_{i+1}_{uuid.uuid4().hex[:4]}", image_bytes)
            results.append(result)
            
            if result["success"]:
                successful += 1
                total_time_sum += result["time"]
            else:
                failed += 1
            
            if delay_between > 0 and i < count - 1:
                time.sleep(delay_between)
        
        avg_time = total_time_sum / successful if successful > 0 else 0
        
        return {
            "count": count,
            "successful": successful,
            "failed": failed,
            "avg_time_per_sample": avg_time,
            "success_rate": (successful / count) * 100 if count > 0 else 0,
            "results": results
        }
    
    def run_single_test(self, count: int, iteration: int) -> Dict:
        """Выполнение одного теста для заданного количества сэмплов"""
        print(f"    Итерация {iteration + 1}...", end=" ", flush=True)
        
        start_time = time.time()
        create_result = self.create_samples_batch(count, delay_between=0.05)
        total_time = time.time() - start_time
        
        result = {
            "iteration": iteration + 1,
            "count": count,
            "successful": create_result["successful"],
            "failed": create_result["failed"],
            "success_rate": create_result["success_rate"],
            "avg_time_per_sample": create_result["avg_time_per_sample"],
            "total_time": total_time
        }
        
        print(f"✓ Успешно: {create_result['successful']}/{count}, "
              f"Время: {create_result['avg_time_per_sample']:.3f}с/сэмпл")
        
        self.delete_all_samples()
        time.sleep(1)
        
        return result
    
    def delete_all_samples(self) -> int:
        """Удаление всех сэмплов пользователя"""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        deleted = 0
        skip = 0
        limit = 50
        
        while True:
            try:
                response = requests.get(
                    f"{API_BASE_URL}/api/samples?skip={skip}&limit={limit}",
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code != 200:
                    break
                    
                samples = response.json()
                if not samples:
                    break
                
                for sample in samples:
                    delete_response = requests.delete(
                        f"{API_BASE_URL}/api/samples/{sample['id']}",
                        headers=headers,
                        timeout=10
                    )
                    if delete_response.status_code == 200:
                        deleted += 1
                
                skip += limit
                time.sleep(0.1)
                
            except Exception as e:
                print(f"  Ошибка при удалении: {e}")
                break
        
        if deleted > 0:
            print(f"  🗑 Удалено {deleted} сэмплов")
        
        return deleted
    
    def run_load_test(self, sample_counts: List[int], iterations: int = 10):
        """Запуск нагрузочного теста с множественными итерациями"""
        print("="*70)
        print("ЗАПУСК НАГРУЗОЧНОГО ТЕСТИРОВАНИЯ")
        print(f"Количество итераций для каждого значения: {iterations}")
        print("="*70)
        
        if not self.register_if_needed():
            print("Не удалось создать/войти в аккаунт")
            return {}
        
        all_results = {}
        
        for count in sample_counts:
            print(f"\n{'='*70}")
            print(f"ТЕСТ ДЛЯ {count} СЭМПЛОВ ({iterations} итераций)")
            print(f"{'='*70}")
            
            iteration_results = []
            
            for iteration in range(iterations):
                result = self.run_single_test(count, iteration)
                iteration_results.append(result)
            
            # Вычисляем средние значения
            successful_counts = [r["successful"] for r in iteration_results]
            success_rates = [r["success_rate"] for r in iteration_results]
            avg_times = [r["avg_time_per_sample"] for r in iteration_results]
            total_times = [r["total_time"] for r in iteration_results]
            
            avg_result = {
                "count": count,
                "iterations": iterations,
                "average_successful": statistics.mean(successful_counts),
                "std_successful": statistics.stdev(successful_counts) if len(successful_counts) > 1 else 0,
                "average_success_rate": statistics.mean(success_rates),
                "std_success_rate": statistics.stdev(success_rates) if len(success_rates) > 1 else 0,
                "average_time_per_sample": statistics.mean(avg_times),
                "std_time_per_sample": statistics.stdev(avg_times) if len(avg_times) > 1 else 0,
                "average_total_time": statistics.mean(total_times),
                "std_total_time": statistics.stdev(total_times) if len(total_times) > 1 else 0,
                "all_iterations": iteration_results
            }
            
            all_results[count] = avg_result
            
            print(f"\n  📊 СВОДКА ДЛЯ {count} СЭМПЛОВ:")
            print(f"    Успешно создано (ср): {avg_result['average_successful']:.1f} ± {avg_result['std_successful']:.1f}")
            print(f"    Успешность: {avg_result['average_success_rate']:.1f}% ± {avg_result['std_success_rate']:.1f}%")
            print(f"    Время на сэмпл: {avg_result['average_time_per_sample']:.3f} ± {avg_result['std_time_per_sample']:.3f} сек")
            print(f"    Общее время: {avg_result['average_total_time']:.2f} ± {avg_result['std_total_time']:.2f} сек")
        
        return all_results
    
    def analyze_complexity(self, results: Dict):
        """Анализ временной сложности алгоритмов"""
        print("\n" + "="*70)
        print("АНАЛИЗ ВРЕМЕННОЙ СЛОЖНОСТИ (на основе усредненных данных)")
        print("="*70)
        
        counts = sorted(results.keys())
        times = [results[c]["average_time_per_sample"] for c in counts]
        total_times = [results[c]["average_total_time"] for c in counts]
        
        time_stds = [results[c]["std_time_per_sample"] for c in counts]
        total_time_stds = [results[c]["std_total_time"] for c in counts]
        
        print("\n📈 Анализ роста времени:")
        print(f"{'Кол-во':<8} {'Время/сэмпл':<18} {'Рост времени':<18} {'Общее время':<18} {'Рост общего':<18}")
        print("-" * 80)
        
        for i, count in enumerate(counts):
            time_str = f"{times[i]:.4f}с"
            total_time_str = f"{total_times[i]:.2f}с"
            
            if i > 0:
                time_growth = times[i] / times[i-1] if times[i-1] > 0 else 0
                count_growth = counts[i] / counts[i-1]
                total_time_growth = total_times[i] / total_times[i-1] if total_times[i-1] > 0 else 0
                
                time_growth_str = f"x{time_growth:.2f} (рост в {count_growth:.1f}x)"
                total_growth_str = f"x{total_time_growth:.2f}"
            else:
                time_growth_str = "-"
                total_growth_str = "-"
            
            print(f"{count:<8} {time_str:<18} {time_growth_str:<18} {total_time_str:<18} {total_growth_str:<18}")
        
        # Определение сложности
        if len(counts) >= 2:
            time_growths = [times[i+1] / times[i] for i in range(len(times)-1) if times[i] > 0]
            count_growths = [counts[i+1] / counts[i] for i in range(len(counts)-1)]
            
            if time_growths:
                avg_growth_ratio = statistics.mean([t / c for t, c in zip(time_growths, count_growths)])
                
                print(f"\n📐 Теоретическая оценка временной сложности:")
                print(f"  Среднее отношение роста времени к росту данных: {avg_growth_ratio:.3f}")
                
                if avg_growth_ratio > 1.2:
                    complexity = "O(n²) или выше (суперлинейный рост)"
                    print(f"  ⚠ Время растет быстрее количества данных - возможны проблемы с производительностью")
                elif avg_growth_ratio > 0.8:
                    complexity = "O(n) - линейная сложность"
                    print(f"  ✓ Линейная зависимость время ~ количество данных")
                elif avg_growth_ratio > 0.5:
                    complexity = "O(log n) - логарифмическая сложность"
                    print(f"  ✓ Хорошая производительность, время растет медленнее данных")
                else:
                    complexity = "O(1) - константная сложность"
                    print(f"  ✓ Отличная производительность, время не зависит от объема данных")
                
                print(f"\n  Вывод: {complexity}")
                
                # Предсказание для больших объемов
                if len(counts) >= 2:
                    last_time = times[-1]
                    last_count = counts[-1]
                    slope = (times[-1] - times[0]) / (counts[-1] - counts[0]) if counts[-1] != counts[0] else 0
                    
                    print(f"\n🔮 Прогноз для больших объемов:")
                    print(f"  При {last_count} сэмплах: ~{last_time:.4f} сек/сэмпл")
                    print(f"  При {last_count * 2} сэмплах: ~{last_time + slope * last_count:.4f} сек/сэмпл (при линейном росте)")
        
        # Построение графиков
        self.plot_results(counts, times, total_times, time_stds, total_time_stds)
    
    def plot_results(self, counts, times, total_times, time_stds, total_time_stds):
        """Построение графиков с error bars"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        
        # График 1: Среднее время на сэмпл
        ax1 = axes[0]
        ax1.errorbar(counts, times, yerr=time_stds, fmt='bo-', 
                    capsize=5, linewidth=2, markersize=8, elinewidth=1)
        ax1.set_xlabel('Количество сэмплов', fontsize=12)
        ax1.set_ylabel('Среднее время на сэмпл (сек)', fontsize=12)
        ax1.set_title('Зависимость времени создания от количества сэмплов', fontsize=14)
        ax1.grid(True, alpha=0.3)
        
        if len(counts) > 1:
            z = np.polyfit(counts, times, 1)
            p = np.poly1d(z)
            ax1.plot(counts, p(counts), "r--", alpha=0.8, 
                    label=f'Тренд: y={z[0]:.6f}x+{z[1]:.4f}')
            ax1.legend()
        
        # График 2: Общее время
        ax2 = axes[1]
        ax2.errorbar(counts, total_times, yerr=total_time_stds, fmt='go-', 
                    capsize=5, linewidth=2, markersize=8, elinewidth=1)
        ax2.set_xlabel('Количество сэмплов', fontsize=12)
        ax2.set_ylabel('Общее время (сек)', fontsize=12)
        ax2.set_title('Зависимость общего времени от количества сэмплов', fontsize=14)
        ax2.grid(True, alpha=0.3)
        
        if len(counts) > 1:
            z2 = np.polyfit(counts, total_times, 1)
            p2 = np.poly1d(z2)
            ax2.plot(counts, p2(counts), "r--", alpha=0.8,
                    label=f'Тренд: y={z2[0]:.4f}x+{z2[1]:.2f}')
            ax2.legend()
        
        plt.tight_layout()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"load_test_results_{timestamp}.png"
        plt.savefig(filename, dpi=100)
        print(f"\n📊 График сохранен в {filename}")
        plt.show()
    
    def save_results_to_json(self, results: Dict):
        """Сохранение результатов в JSON файл"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"load_test_results_{timestamp}.json"
        
        serializable_results = {}
        for count, data in results.items():
            serializable_results[count] = {
                "count": data["count"],
                "iterations": data["iterations"],
                "average_successful": data["average_successful"],
                "std_successful": data["std_successful"],
                "average_success_rate": data["average_success_rate"],
                "std_success_rate": data["std_success_rate"],
                "average_time_per_sample": data["average_time_per_sample"],
                "std_time_per_sample": data["std_time_per_sample"],
                "average_total_time": data["average_total_time"],
                "std_total_time": data["std_total_time"],
                "all_iterations": data["all_iterations"]
            }
        
        with open(filename, 'w') as f:
            json.dump(serializable_results, f, indent=2, default=str)
        
        print(f"\n💾 Результаты сохранены в {filename}")
        return filename


def main():
    """Основная функция"""
    tester = LoadTester()
    
    try:
        sample_counts = [10, 25, 50, 75, 100]
        iterations = 5
        
        print(f"\n⚠ ВНИМАНИЕ: Тест будет выполнять {iterations} итераций для каждого значения")
        print(f"Всего операций создания сэмплов: {len(sample_counts) * iterations}\n")
        
        results = tester.run_load_test(sample_counts=sample_counts, iterations=iterations)
        
        if results:
            tester.analyze_complexity(results)
            tester.save_results_to_json(results)
        
    except KeyboardInterrupt:
        print("\n\n⚠ Тестирование прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ Тестирование завершено!")


if __name__ == "__main__":
    main()